"""GitHubPort adapter: thin async client over the GitHub REST API (design D6).

Handles auth, pagination, rate-limit backoff, and optional raw-payload
capture to object storage. No third-party GitHub SDK.
"""

import asyncio
import base64
from datetime import UTC, datetime
from typing import Any

import httpx

from app.domain.ports.github_port import (
    GitHubAuthError,
    GitHubFileData,
    GitHubIssueData,
    GitHubNotFoundError,
    GitHubPullRequestData,
    GitHubRepoData,
    GitHubTokenInfo,
)
from app.domain.ports.infra_ports import ObjectStoragePort

API_BASE = "https://api.github.com"
MAX_PAGES = 100  # hard bound: 100 pages x 100 items
_BINARY_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "ico", "pdf", "zip", "tar", "gz", "whl",
    "so", "dylib", "dll", "exe", "bin", "woff", "woff2", "ttf", "eot",
    "mp3", "mp4", "webm", "sqlite", "db", "pyc", "jar", "class",
}  # fmt: skip


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GitHubClient:
    """Implements GitHubPort against api.github.com."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        storage: ObjectStoragePort | None = None,
        base_url: str = API_BASE,
        max_rate_limit_waits: int = 3,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=30)
        self._storage = storage
        self._base_url = base_url
        self._max_rate_limit_waits = max_rate_limit_waits

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(self, method: str, url: str, token: str, **kwargs: Any) -> httpx.Response:
        """Single request with rate-limit sleep-until-reset (design D6)."""
        for _ in range(self._max_rate_limit_waits + 1):
            response = await self._client.request(
                method, url, headers=self._headers(token), **kwargs
            )
            if response.status_code in (403, 429) and (
                response.headers.get("X-RateLimit-Remaining") == "0"
                or "rate limit" in response.text.lower()
            ):
                reset = int(response.headers.get("X-RateLimit-Reset", "0"))
                delay = max(1.0, reset - datetime.now(UTC).timestamp() + 1)
                await asyncio.sleep(min(delay, 3600))
                continue
            break
        if response.status_code == 401:
            raise GitHubAuthError("GitHub rejected the credential")
        if response.status_code == 404:
            raise GitHubNotFoundError(url)
        response.raise_for_status()
        return response

    async def _paginate(
        self, url: str, token: str, params: dict[str, Any] | None = None
    ) -> list[Any]:
        items: list[Any] = []
        params = {"per_page": 100, **(params or {})}
        next_url: str | None = f"{self._base_url}{url}"
        for _ in range(MAX_PAGES):
            if next_url is None:
                break
            response = await self._request("GET", next_url, token, params=params)
            params = None  # subsequent pages carry params in the Link URL
            page = response.json()
            items.extend(page if isinstance(page, list) else [page])
            next_url = response.links.get("next", {}).get("url")
        return items

    async def _snapshot(self, key: str, payload: Any) -> None:
        """Raw payloads land in object storage before normalization (spec: repository-sync)."""
        if self._storage is not None:
            await self._storage.put_json(key, payload)

    # -- GitHubPort ---------------------------------------------------------

    async def validate_token(self, token: str) -> GitHubTokenInfo:
        response = await self._request("GET", f"{self._base_url}/user", token)
        user = response.json()
        # Fine-grained PATs don't expose a scope header; probe the API surface
        permissions = {"metadata"}
        for probe, permission in [
            ("/user/repos?per_page=1", "contents"),
            ("/issues?per_page=1&filter=all", "issues"),
        ]:
            try:
                await self._request("GET", f"{self._base_url}{probe}", token)
                permissions.add(permission)
            except (GitHubAuthError, GitHubNotFoundError, httpx.HTTPStatusError):
                continue
        if "contents" in permissions:
            # repo listing implies PR read access on fine-grained repo grants
            permissions.update({"pull_requests"})
        return GitHubTokenInfo(
            login=user["login"],
            owner_type=user.get("type", "User"),
            permissions=permissions,
        )

    async def list_repositories(self, token: str) -> list[GitHubRepoData]:
        raw = await self._paginate(
            "/user/repos",
            token,
            params={"sort": "updated", "affiliation": "owner,organization_member"},
        )
        return [
            GitHubRepoData(
                github_id=r["id"],
                full_name=r["full_name"],
                description=r.get("description"),
                visibility=r.get("visibility", "private" if r.get("private") else "public"),
                default_branch=r.get("default_branch", "main"),
                primary_language=r.get("language"),
                archived=r.get("archived", False),
                updated_at=_parse_dt(r.get("updated_at")),
            )
            for r in raw
        ]

    async def get_repository(self, token: str, full_name: str) -> GitHubRepoData:
        response = await self._request("GET", f"{self._base_url}/repos/{full_name}", token)
        r = response.json()
        await self._snapshot(f"raw/github/repos/{full_name}/metadata.json", r)
        return GitHubRepoData(
            github_id=r["id"],
            full_name=r["full_name"],
            description=r.get("description"),
            visibility=r.get("visibility", "private" if r.get("private") else "public"),
            default_branch=r.get("default_branch", "main"),
            primary_language=r.get("language"),
            archived=r.get("archived", False),
            updated_at=_parse_dt(r.get("updated_at")),
        )

    async def get_file_content(self, token: str, full_name: str, path: str) -> str:
        response = await self._request(
            "GET", f"{self._base_url}/repos/{full_name}/contents/{path}", token
        )
        payload = response.json()
        if payload.get("encoding") == "base64":
            return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        return str(payload.get("content", ""))

    async def get_tree(self, token: str, full_name: str, branch: str) -> list[GitHubFileData]:
        response = await self._request(
            "GET",
            f"{self._base_url}/repos/{full_name}/git/trees/{branch}",
            token,
            params={"recursive": "1"},
        )
        payload = response.json()
        await self._snapshot(f"raw/github/repos/{full_name}/tree.json", payload)
        files = []
        for node in payload.get("tree", []):
            if node.get("type") != "blob":
                continue
            path = node["path"]
            extension = path.rsplit(".", 1)[-1].lower() if "." in path.split("/")[-1] else ""
            files.append(
                GitHubFileData(
                    path=path,
                    sha=node.get("sha", ""),
                    size=node.get("size", 0),
                    is_binary=extension in _BINARY_EXTENSIONS,
                )
            )
        return files

    async def list_issues(self, token: str, full_name: str) -> list[GitHubIssueData]:
        raw = await self._paginate(
            f"/repos/{full_name}/issues", token, params={"state": "all"}
        )
        await self._snapshot(f"raw/github/repos/{full_name}/issues.json", raw)
        return [
            GitHubIssueData(
                github_id=i["id"],
                number=i["number"],
                title=i["title"],
                body=i.get("body"),
                state=i["state"],
                author=(i.get("user") or {}).get("login"),
                labels=[
                    lb["name"] if isinstance(lb, dict) else str(lb) for lb in i.get("labels", [])
                ],
                assignees=[a["login"] for a in i.get("assignees", [])],
                milestone=(i.get("milestone") or {}).get("title"),
                created_at=_parse_dt(i.get("created_at")),
                updated_at=_parse_dt(i.get("updated_at")),
                closed_at=_parse_dt(i.get("closed_at")),
                comments_count=i.get("comments", 0),
                is_pull_request="pull_request" in i,
            )
            for i in raw
        ]

    async def list_pull_requests(self, token: str, full_name: str) -> list[GitHubPullRequestData]:
        raw = await self._paginate(
            f"/repos/{full_name}/pulls", token, params={"state": "all"}
        )
        await self._snapshot(f"raw/github/repos/{full_name}/prs.json", raw)
        results = []
        for p in raw:
            reviews = await self._paginate(
                f"/repos/{full_name}/pulls/{p['number']}/reviews", token
            )
            review_times = [
                t for r in reviews if (t := _parse_dt(r.get("submitted_at"))) is not None
            ]
            results.append(
                GitHubPullRequestData(
                    github_id=p["id"],
                    number=p["number"],
                    title=p["title"],
                    body=p.get("body"),
                    state="merged" if p.get("merged_at") else p["state"],
                    merged=bool(p.get("merged_at")),
                    author=(p.get("user") or {}).get("login"),
                    reviewers=sorted(
                        {
                            login
                            for r in reviews
                            if (login := (r.get("user") or {}).get("login"))
                        }
                    ),
                    created_at=_parse_dt(p.get("created_at")),
                    updated_at=_parse_dt(p.get("updated_at")),
                    closed_at=_parse_dt(p.get("closed_at")),
                    merged_at=_parse_dt(p.get("merged_at")),
                    first_review_at=min(review_times) if review_times else None,
                    changed_files=p.get("changed_files", 0),
                    additions=p.get("additions", 0),
                    deletions=p.get("deletions", 0),
                    review_decision=reviews[-1].get("state") if reviews else None,
                )
            )
        return results

    async def get_rate_limit(self, token: str) -> dict[str, int]:
        response = await self._request("GET", f"{self._base_url}/rate_limit", token)
        core = response.json().get("resources", {}).get("core", {})
        return {"limit": core.get("limit", 0), "remaining": core.get("remaining", 0)}

    async def close(self) -> None:
        await self._client.aclose()
