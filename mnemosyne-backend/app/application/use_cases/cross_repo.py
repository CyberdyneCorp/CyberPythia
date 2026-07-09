"""Cross-repository agent tools (spec: mcp-interface).

Aggregations that span many repositories so agents can work at the portfolio /
organization level without looping every repo: fuzzy repo resolution, global
search, cross-repo stale finders, and a recent-activity feed.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.entities.repository import Repository
from app.domain.ports.infra_ports import EmbeddingPort
from app.domain.ports.persistence_ports import IssuePort, PullRequestPort, RepositoryPort


@dataclass(slots=True)
class CrossRepoService:
    repositories: RepositoryPort
    issues: IssuePort
    pull_requests: PullRequestPort
    embeddings: EmbeddingPort

    async def _scoped_repos(self, organization: str | None) -> list[Repository]:
        repos = await self.repositories.list_all(enabled_only=True)
        if organization:
            owner = organization.lower()
            repos = [r for r in repos if r.full_name.owner.lower() == owner]
        return repos

    # -- global / org search --------------------------------------------------

    async def search(
        self, query: str, *, kind: str = "docs", organization: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Search across repositories. kind: docs | code | issues.

        docs/code are semantic (one embedded query over all matching repos); issues
        are keyword-ranked. Results carry the repository `full_name`.
        """
        repos = await self._scoped_repos(organization)
        names = {r.id: str(r.full_name) for r in repos}
        repo_ids = list(names) if organization else None  # None = every indexed repo

        if kind == "docs":
            matches = await self.embeddings.search_global(
                query, repository_ids=repo_ids, limit=limit
            )
            return [
                {"repository_id": str(m.repository_id), "full_name": _name(names, m.repository_id),
                 "path": m.path, "title": m.title, "excerpt": m.excerpt,
                 "score": round(m.score, 3)}
                for m in matches
            ]
        if kind == "code":
            code = await self.embeddings.search_code_global(
                query, repository_ids=repo_ids, limit=limit
            )
            return [
                {"repository_id": str(m.repository_id), "full_name": _name(names, m.repository_id),
                 "path": m.path, "symbol": m.symbol_name, "start_line": m.start_line,
                 "excerpt": m.excerpt, "score": round(m.score, 3)}
                for m in code
            ]
        if kind == "issues":
            return await self._search_issues(query, repos, limit)
        raise ValueError(f"unknown search kind '{kind}' (expected docs|code|issues)")

    async def _search_issues(
        self, query: str, repos: list[Repository], limit: int
    ) -> list[dict[str, Any]]:
        terms = [t for t in query.strip().lower().split() if t]
        hits: list[tuple[int, dict[str, Any]]] = []
        for repo in repos:
            for issue in await self.issues.list_by_repository(repo.id):
                hay = f"{issue.title} {issue.body or ''} {' '.join(issue.labels)}".lower()
                score = sum(hay.count(t) for t in terms)
                if score:
                    hits.append((score, {
                        "repository_id": str(repo.id),
                        "full_name": str(repo.full_name), "number": issue.number,
                        "title": issue.title, "state": issue.state.value,
                        "labels": issue.labels, "score": score,
                    }))
        hits.sort(key=lambda h: -h[0])
        return [h[1] for h in hits[:limit]]

    # -- fuzzy repository resolver -------------------------------------------

    async def find_repositories(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Rank indexed repositories against a fuzzy query (name > full name > desc > lang)."""
        terms = [t for t in query.strip().lower().split() if t]
        repos = await self.repositories.list_all(enabled_only=True)
        scored: list[tuple[int, Repository]] = []
        for r in repos:
            full = str(r.full_name).lower()
            name = r.full_name.name.lower()
            desc = (r.description or "").lower()
            lang = (r.primary_language or "").lower()
            score = 0
            for t in terms:
                if t in (name, full):
                    score += 100
                elif t in name:
                    score += 10
                elif t in full:
                    score += 5
                if t in desc:
                    score += 2
                if t in lang:
                    score += 1
            if score:
                scored.append((score, r))
        scored.sort(key=lambda sr: (-sr[0], str(sr[1].full_name).lower()))
        return [_repo_brief(r) for _, r in scored[:limit]]

    # -- cross-repo stale finders --------------------------------------------

    async def find_stale_issues(
        self, *, organization: str | None = None, threshold_days: int = 30,
        limit: int = 50, now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(days=threshold_days)
        out: list[dict[str, Any]] = []
        for repo in await self._scoped_repos(organization):
            for issue in await self.issues.list_by_repository(repo.id, state="open"):
                ts = issue.updated_at or issue.created_at
                if ts is not None and ts < cutoff:
                    out.append({
                        "repository_id": str(repo.id),
                        "full_name": str(repo.full_name), "number": issue.number,
                        "title": issue.title, "labels": issue.labels,
                        "updated_at": ts.isoformat(),
                        "stale_days": (now - ts).days,
                    })
        out.sort(key=lambda i: i["updated_at"])  # oldest first
        return out[:limit]

    async def find_stale_prs(
        self, *, organization: str | None = None, threshold_days: int = 30,
        limit: int = 50, now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(days=threshold_days)
        out: list[dict[str, Any]] = []
        for repo in await self._scoped_repos(organization):
            for pr in await self.pull_requests.list_by_repository(repo.id, state="open"):
                ts = pr.updated_at or pr.created_at
                if ts is not None and ts < cutoff:
                    out.append({
                        "repository_id": str(repo.id),
                        "full_name": str(repo.full_name), "number": pr.number,
                        "title": pr.title, "author": pr.author,
                        "updated_at": ts.isoformat(), "stale_days": (now - ts).days,
                    })
        out.sort(key=lambda p: p["updated_at"])
        return out[:limit]

    # -- recent activity feed -------------------------------------------------

    async def recent_activity(
        self, *, organization: str | None = None, limit: int = 15,
    ) -> dict[str, Any]:
        repos = await self._scoped_repos(organization)
        synced = sorted(
            (r for r in repos if r.last_synced_at is not None),
            key=lambda r: r.last_synced_at, reverse=True,  # type: ignore[arg-type,return-value]
        )
        issues: list[dict[str, Any]] = []
        prs: list[dict[str, Any]] = []
        for repo in repos:
            for issue in await self.issues.list_by_repository(repo.id):
                if issue.updated_at is not None:
                    issues.append({
                        "repository_id": str(repo.id),
                        "full_name": str(repo.full_name), "number": issue.number,
                        "title": issue.title, "state": issue.state.value,
                        "updated_at": issue.updated_at.isoformat(),
                    })
            for pr in await self.pull_requests.list_by_repository(repo.id):
                if pr.updated_at is not None:
                    prs.append({
                        "repository_id": str(repo.id),
                        "full_name": str(repo.full_name), "number": pr.number,
                        "title": pr.title, "state": pr.state.value, "merged": pr.merged,
                        "updated_at": pr.updated_at.isoformat(),
                    })
        issues.sort(key=lambda i: i["updated_at"], reverse=True)
        prs.sort(key=lambda p: p["updated_at"], reverse=True)
        return {
            "recently_synced": [
                {"repository_id": str(r.id), "full_name": str(r.full_name),
                 "last_synced_at": r.last_synced_at.isoformat()}  # type: ignore[union-attr]
                for r in synced[:limit]
            ],
            "recent_issues": issues[:limit],
            "recent_pull_requests": prs[:limit],
        }


def _name(names: dict[Any, str], repository_id: Any) -> str:
    result: str = names.get(repository_id, str(repository_id))
    return result


def _repo_brief(r: Repository) -> dict[str, Any]:
    return {
        "repository_id": str(r.id),
        "full_name": str(r.full_name),
        "description": r.description,
        "primary_language": r.primary_language,
        "indexing_mode": r.indexing_mode.value,
        "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
    }
