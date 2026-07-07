"""FastMCP server: Mnemosyne tools for agents (spec: mcp-interface).

Runs as its own service (`mnemosyne-mcp`) over streamable HTTP, sharing
the domain layer and CyberdyneAuth verification with the REST API.

Errors are structured dicts (`{"error": {"code", "message"}}`) so calling
agents can branch on them instead of parsing free text.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers

from app.application.errors import ApplicationError, RepositoryNotSyncedError
from app.composition import Container, build_container
from app.config import get_settings
from app.domain.entities.repository import Repository
from app.domain.ports.auth_port import AuthUnavailableError, TokenInvalidError
from app.domain.services.issue_metrics import IssueMetricsService
from app.domain.services.pr_metrics import PullRequestMetricsService
from app.domain.value_objects.identity import CallerIdentity

logger = logging.getLogger(__name__)

Authenticator = Callable[[], Awaitable[CallerIdentity]]


def _error(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def build_mcp(
    container: Container | None = None, authenticate: Authenticator | None = None
) -> FastMCP:
    container = container or build_container()
    settings = get_settings()

    async def default_authenticate() -> CallerIdentity:
        # include_all: FastMCP strips `authorization` from the default header view
        headers = get_http_headers(include_all=True)
        authorization = headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            raise ToolError("unauthenticated: missing bearer token")
        token = authorization.split(" ", 1)[1]
        try:
            caller = await container.auth_port.verify(token)
        except TokenInvalidError as exc:
            await container.audit_service.record_denied(None, "mcp.auth")
            raise ToolError("unauthenticated: invalid token") from exc
        except AuthUnavailableError as exc:
            raise ToolError("auth_unavailable: authentication service unreachable") from exc
        if not caller.can_access(settings.required_entitlement):
            await container.audit_service.record_denied(caller, "mcp.access")
            raise ToolError(
                f"missing_entitlement: caller lacks the "
                f"'{settings.required_entitlement}' entitlement"
            )
        return caller

    auth = authenticate or default_authenticate

    mcp: FastMCP = FastMCP(
        name="Mnemosyne",
        instructions=(
            "GitHub context & memory layer. Tools answer questions about indexed "
            "repositories: documentation, OpenSpec changes, issues, pull requests, "
            "engineering metrics, and task-specific context packs. Repositories are "
            "addressed by full name (owner/name). All tools require a CyberdyneAuth "
            "bearer token with the 'mnemosyne' entitlement."
        ),
    )

    async def _resolve_repo(full_name: str) -> Repository | dict[str, Any]:
        repository = await container.repositories.get_by_full_name(full_name)
        if repository is None or not repository.enabled:
            return _error(
                "unknown_repository",
                f"repository '{full_name}' is not indexed by Mnemosyne",
            )
        if repository.last_synced_at is None:
            return _error(
                "repository_not_synced",
                f"repository '{full_name}' has never completed a sync — "
                "ask an admin to trigger one",
            )
        return repository

    # -- repository tools ------------------------------------------------------

    @mcp.tool
    async def mnemosyne_list_repositories() -> list[dict[str, Any]]:
        """List repositories indexed by Mnemosyne with sync freshness."""
        await auth()
        repos = await container.repositories.list_all(enabled_only=True)
        return [
            {
                "full_name": str(r.full_name),
                "description": r.description,
                "primary_language": r.primary_language,
                "indexing_mode": r.indexing_mode.value,
                "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
            }
            for r in repos
        ]

    @mcp.tool
    async def mnemosyne_get_repository_summary(full_name: str) -> dict[str, Any]:
        """Get the indexed summary of a repository: metadata, docs presence, headline metrics."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        metrics = await container.metrics_store.get(repository.id)
        return {
            "full_name": str(repository.full_name),
            "description": repository.description,
            "primary_language": repository.primary_language,
            "default_branch": repository.default_branch,
            "indexing_mode": repository.indexing_mode.value,
            "last_synced_at": repository.last_synced_at.isoformat()
            if repository.last_synced_at
            else None,
            "summary": (metrics or {}).get("summary"),
        }

    @mcp.tool
    async def mnemosyne_get_repository_tree(full_name: str) -> dict[str, Any]:
        """Get the captured file tree (mode code_metadata only)."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        if not repository.indexing_mode.includes_file_tree:
            return _error(
                "mode_excludes_content",
                f"indexing mode '{repository.indexing_mode.value}' does not capture file trees",
            )
        files = await container.files.list_by_repository(repository.id)
        return {
            "full_name": full_name,
            "files": [
                {
                    "path": f.path,
                    "language": f.language,
                    "size_bytes": f.size_bytes,
                    "important_kind": f.important_kind,
                }
                for f in files
            ],
        }

    # -- documentation tools ----------------------------------------------------

    @mcp.tool
    async def mnemosyne_get_readme(full_name: str) -> dict[str, Any]:
        """Get the repository README content."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        docs = await container.documents.list_by_repository(repository.id)
        readme = next((d for d in docs if d.type.value == "README"), None)
        if readme is None:
            return _error("not_found", f"no README captured for '{full_name}'")
        return {"path": readme.path, "title": readme.title, "content": readme.content}

    @mcp.tool
    async def mnemosyne_get_docs_index(full_name: str) -> list[dict[str, Any]] | dict[str, Any]:
        """List captured documentation files (path, type, title) for a repository."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        docs = await container.documents.list_by_repository(repository.id)
        return [
            {"path": d.path, "type": d.type.value, "title": d.title, "quarantined": d.quarantined}
            for d in docs
        ]

    @mcp.tool
    async def mnemosyne_search_docs(
        full_name: str, query: str, limit: int = 8
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Semantic search over a repository's documentation."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        matches = await container.embeddings.search(
            repository.id, query, limit=max(1, min(limit, 25))
        )
        return [
            {
                "path": m.path,
                "title": m.title,
                "doc_type": m.doc_type,
                "excerpt": m.excerpt,
                "score": round(m.score, 4),
            }
            for m in matches
        ]

    @mcp.tool
    async def mnemosyne_get_openspec_context(full_name: str) -> dict[str, Any]:
        """Get the repository's OpenSpec changes (proposal/design/tasks, status)."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        changes = await container.openspec.list_by_repository(repository.id)
        return {
            "full_name": full_name,
            "changes": [
                {
                    "change_id": c.change_id,
                    "status": c.status.value,
                    "path": c.path,
                    "proposal": c.proposal,
                    "design": c.design,
                    "tasks": c.tasks,
                    "affected_specs": c.affected_specs,
                }
                for c in changes
            ],
        }

    # -- issue / PR tools ---------------------------------------------------------

    @mcp.tool
    async def mnemosyne_list_issues(
        full_name: str, state: str | None = None, label: str | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """List synced issues, optionally filtered by state (open|closed) or label."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        if not repository.indexing_mode.includes_issues_and_prs:
            return _error(
                "mode_excludes_content",
                f"indexing mode '{repository.indexing_mode.value}' does not capture issues",
            )
        issues = await container.issues.list_by_repository(
            repository.id, state=state, label=label
        )
        return [_issue_dict(i) for i in issues]

    @mcp.tool
    async def mnemosyne_get_issue(full_name: str, number: int) -> dict[str, Any]:
        """Get one issue by number, including body."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        issue = await container.issues.get_by_number(repository.id, number)
        if issue is None:
            return _error("not_found", f"issue #{number} not found in '{full_name}'")
        return {**_issue_dict(issue), "body": issue.body}

    @mcp.tool
    async def mnemosyne_search_issues(
        full_name: str, query: str, limit: int = 10
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Keyword-search issues by title/body/labels, ranked by relevance."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        from app.domain.services.relevance import keyword_score

        issues = await container.issues.list_by_repository(repository.id)
        scored = [
            (keyword_score(query, i.title, i.body, " ".join(i.labels), weights=(2.0, 1.0, 1.0)), i)
            for i in issues
        ]
        top = sorted((s for s in scored if s[0] > 0), key=lambda s: -s[0])[: max(1, limit)]
        return [{**_issue_dict(i), "score": round(score, 4)} for score, i in top]

    @mcp.tool
    async def mnemosyne_get_issue_resolution_metrics(full_name: str) -> dict[str, Any]:
        """Issue metrics: avg/median resolution time, staleness, breakdowns."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        stored = await container.metrics_store.get(repository.id)
        if stored is None:
            return _error("not_found", "metrics not computed yet")
        return {"computed_at": stored["computed_at"], **stored["issue_metrics"]}

    @mcp.tool
    async def mnemosyne_list_pull_requests(
        full_name: str, state: str | None = None, author: str | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """List synced pull requests, optionally filtered by state or author."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        if not repository.indexing_mode.includes_issues_and_prs:
            return _error(
                "mode_excludes_content",
                f"indexing mode '{repository.indexing_mode.value}' does not capture pull requests",
            )
        prs = await container.pull_requests.list_by_repository(
            repository.id, state=state, author=author
        )
        return [_pr_dict(p) for p in prs]

    @mcp.tool
    async def mnemosyne_get_pull_request(full_name: str, number: int) -> dict[str, Any]:
        """Get one pull request by number, including body."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        pr = await container.pull_requests.get_by_number(repository.id, number)
        if pr is None:
            return _error("not_found", f"PR #{number} not found in '{full_name}'")
        return {**_pr_dict(pr), "body": pr.body}

    @mcp.tool
    async def mnemosyne_get_pr_review_metrics(full_name: str) -> dict[str, Any]:
        """PR metrics: merge time, time-to-first-review, merge rate, size distribution."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        stored = await container.metrics_store.get(repository.id)
        if stored is None:
            return _error("not_found", "metrics not computed yet")
        return {"computed_at": stored["computed_at"], **stored["pr_metrics"]}

    @mcp.tool
    async def mnemosyne_find_stale_issues(
        full_name: str, threshold_days: int = 30
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Open issues with no activity beyond the threshold, oldest first."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        issues = await container.issues.list_by_repository(repository.id, state="open")
        metrics = IssueMetricsService(threshold_days).compute(issues, datetime.now(UTC))
        return [asdict(s) for s in metrics.stale_issues]

    @mcp.tool
    async def mnemosyne_find_stale_prs(
        full_name: str, threshold_days: int = 30
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Open pull requests with no activity beyond the threshold, oldest first."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        prs = await container.pull_requests.list_by_repository(repository.id, state="open")
        metrics = PullRequestMetricsService(threshold_days).compute(prs, datetime.now(UTC))
        return [asdict(s) for s in metrics.stale_prs]

    # -- context tools --------------------------------------------------------------

    @mcp.tool
    async def mnemosyne_build_context_pack(full_name: str, task: str) -> dict[str, Any]:
        """Build a task-specific context pack: relevant docs, OpenSpec changes, issues,
        PRs, files, risks, and suggested next steps for an agent about to work on the task."""
        caller = await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        try:
            pack = await container.context_use_cases.build_context_pack(repository.id, task)
        except RepositoryNotSyncedError as exc:
            return _error("repository_not_synced", str(exc))
        except ApplicationError as exc:
            return _error("application_error", str(exc))
        await container.audit_service.record(caller, "mcp.context_pack", target=full_name)
        return {
            "repository": full_name,
            "query": pack.query,
            "mode": pack.mode.value,
            "summary": pack.repository_summary,
            "relevant_docs": [asdict(d) for d in pack.relevant_docs],
            "relevant_openspec_changes": [asdict(o) for o in pack.relevant_openspec_changes],
            "relevant_issues": [asdict(i) for i in pack.relevant_issues],
            "relevant_pull_requests": [asdict(p) for p in pack.relevant_pull_requests],
            "relevant_files": [asdict(f) for f in pack.relevant_files],
            "risks": pack.risks,
            "suggested_next_steps": pack.suggested_next_steps,
            "excluded_categories": pack.excluded_categories,
        }

    @mcp.tool
    async def mnemosyne_answer_from_repo_context(full_name: str, question: str) -> dict[str, Any]:
        """Answer a question about a repository using only indexed context, with citations."""
        caller = await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        try:
            result = await container.context_use_cases.ask(repository.id, question)
        except RepositoryNotSyncedError as exc:
            return _error("repository_not_synced", str(exc))
        except ApplicationError as exc:
            return _error("application_error", str(exc))
        await container.audit_service.record(caller, "mcp.ask", target=full_name)
        return result

    return mcp


def _issue_dict(issue: Any) -> dict[str, Any]:
    return {
        "number": issue.number,
        "title": issue.title,
        "state": issue.state.value,
        "author": issue.author,
        "labels": issue.labels,
        "assignees": issue.assignees,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
        "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
        "resolution_time_seconds": issue.resolution_time_seconds,
        "comments_count": issue.comments_count,
    }


def _pr_dict(pr: Any) -> dict[str, Any]:
    return {
        "number": pr.number,
        "title": pr.title,
        "state": pr.state.value,
        "merged": pr.merged,
        "author": pr.author,
        "reviewers": pr.reviewers,
        "created_at": pr.created_at.isoformat() if pr.created_at else None,
        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
        "time_to_merge_seconds": pr.time_to_merge_seconds,
        "time_to_first_review_seconds": pr.time_to_first_review_seconds,
        "additions": pr.additions,
        "deletions": pr.deletions,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp = build_mcp()
    mcp.run(transport="http", host="0.0.0.0", port=get_settings().mcp_port)


if __name__ == "__main__":
    main()
