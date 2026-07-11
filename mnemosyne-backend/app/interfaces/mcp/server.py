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
from fastmcp.server.dependencies import get_access_token, get_http_headers

from app.application.errors import ApplicationError, RepositoryNotSyncedError
from app.application.use_cases.context import FEATURE_DOCUMENT_PROMPT
from app.application.use_cases.org_intelligence import build_org_intelligence
from app.composition import Container, build_container
from app.config import get_settings
from app.domain.entities.repository import Repository
from app.domain.ports.auth_port import AuthUnavailableError, TokenInvalidError
from app.domain.services.issue_metrics import IssueMetricsService
from app.domain.services.pr_metrics import PullRequestMetricsService
from app.domain.value_objects.identity import CallerIdentity
from app.interfaces.mcp.oauth import build_mcp_auth, caller_from_access_token

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
        # When OAuth is on, the transport already verified the bearer via the
        # CompositeTokenVerifier and stashed the caller — reuse it (no re-verify).
        cached = caller_from_access_token(get_access_token())
        if cached is not None:
            return cached
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
        if not caller.can_access(settings.required_entitlement, settings.service_audience):
            await container.audit_service.record_denied(caller, "mcp.access")
            raise ToolError(
                f"missing_entitlement: caller lacks the "
                f"'{settings.required_entitlement}' entitlement"
            )
        return caller

    auth = authenticate or default_authenticate

    # Attach the OAuthProxy so DCR-only clients (claude.ai) can obtain a token.
    # Additive: its verifier delegates to auth_port, so API keys + bearers still
    # authenticate. Disabled by default → today's behavior is unchanged.
    oauth_provider = None
    if settings.mcp_oauth_enabled:
        oauth_provider = build_mcp_auth(container.auth_port, settings)

    mcp: FastMCP = FastMCP(
        name="Mnemosyne",
        auth=oauth_provider,
        instructions=(
            "GitHub context & memory layer. Tools answer questions about indexed "
            "repositories: documentation, OpenSpec changes, issues, pull requests, "
            "engineering metrics, and task-specific context packs. Repositories are "
            "addressed by full name (owner/name). All tools require a CyberdyneAuth "
            "bearer token with the 'mnemosyne' entitlement, or a Mnemosyne API key."
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
    async def mnemosyne_list_organizations() -> list[dict[str, Any]]:
        """List the organizations Mnemosyne has discovered, with repository counts."""
        await auth()
        repos = await container.repositories.list_all()
        stats: dict[str, dict[str, int]] = {}
        for r in repos:
            s = stats.setdefault(r.full_name.owner, {"total": 0, "indexed": 0})
            s["total"] += 1
            if r.enabled:
                s["indexed"] += 1
        return [
            {"login": login, "total_repos": s["total"], "indexed_repos": s["indexed"]}
            for login, s in sorted(stats.items(), key=lambda kv: kv[0].lower())
        ]

    @mcp.tool
    async def mnemosyne_list_organization_repositories(
        organization: str,
    ) -> list[dict[str, Any]]:
        """List every repository discovered in an organization (readable by the credential)."""
        await auth()
        owner = organization.lower()
        repos = [
            r
            for r in await container.repositories.list_all()
            if r.full_name.owner.lower() == owner
        ]
        return [
            {
                "full_name": str(r.full_name),
                "description": r.description,
                "primary_language": r.primary_language,
                "indexed": r.enabled,
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

    # -- code tools -----------------------------------------------------------------

    async def _code_error(exc: ApplicationError) -> dict[str, Any]:
        from app.application.errors import (
            ContentUnavailableError,
            SourceNotIndexedError,
            UnknownResourceError,
        )
        from app.application.errors import (
            RepositoryNotSyncedError as _NotSynced,
        )

        if isinstance(exc, SourceNotIndexedError):
            return _error("mode_excludes_content", str(exc))
        if isinstance(exc, _NotSynced):
            return _error("repository_not_synced", str(exc))
        if isinstance(exc, ContentUnavailableError):
            return _error("content_unavailable", str(exc))
        if isinstance(exc, UnknownResourceError):
            return _error("not_found", str(exc))
        return _error("application_error", str(exc))

    @mcp.tool
    async def mnemosyne_search_code(
        full_name: str, query: str, limit: int = 8
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Semantic search over a repository's source code (mode code_context/full_context)."""
        await auth()
        repository = await container.repositories.get_by_full_name(full_name)
        if repository is None or not repository.enabled:
            return _error("unknown_repository", f"repository '{full_name}' is not indexed")
        try:
            matches = await container.code_use_cases.search_code(
                repository.id, query, limit=max(1, min(limit, 25))
            )
        except ApplicationError as exc:
            return await _code_error(exc)
        return [
            {
                "path": m.path,
                "symbol_name": m.symbol_name,
                "chunk_type": m.chunk_type,
                "start_line": m.start_line,
                "end_line": m.end_line,
                "excerpt": m.excerpt,
                "score": round(m.score, 4),
            }
            for m in matches
        ]

    @mcp.tool
    async def mnemosyne_get_symbol_context(
        full_name: str, symbol_name: str
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Look up source chunks defining a symbol by name."""
        await auth()
        repository = await container.repositories.get_by_full_name(full_name)
        if repository is None or not repository.enabled:
            return _error("unknown_repository", f"repository '{full_name}' is not indexed")
        try:
            return await container.code_use_cases.symbols(repository.id, symbol_name)
        except ApplicationError as exc:
            return await _code_error(exc)

    @mcp.tool
    async def mnemosyne_get_file_content(full_name: str, path: str) -> dict[str, Any]:
        """Get the captured content of a source file by path."""
        caller = await auth()
        repository = await container.repositories.get_by_full_name(full_name)
        if repository is None or not repository.enabled:
            return _error("unknown_repository", f"repository '{full_name}' is not indexed")
        file = await container.files.get_by_path(repository.id, path)
        if file is None:
            return _error("not_found", f"file '{path}' not found in '{full_name}'")
        try:
            return await container.code_use_cases.file_content(repository.id, file.id, caller)
        except ApplicationError as exc:
            return await _code_error(exc)

    @mcp.tool
    async def mnemosyne_get_related_files(full_name: str, path: str) -> dict[str, Any]:
        """Find files related to a given file via import/reference heuristics."""
        await auth()
        repository = await container.repositories.get_by_full_name(full_name)
        if repository is None or not repository.enabled:
            return _error("unknown_repository", f"repository '{full_name}' is not indexed")
        file = await container.files.get_by_path(repository.id, path)
        if file is None:
            return _error("not_found", f"file '{path}' not found in '{full_name}'")
        try:
            return await container.code_use_cases.related_files(repository.id, file.id)
        except ApplicationError as exc:
            return await _code_error(exc)

    @mcp.tool
    async def mnemosyne_explain_repository_structure(full_name: str) -> dict[str, Any]:
        """Summarize the tree, languages, important files, and (code modes) key symbols."""
        await auth()
        repository = await container.repositories.get_by_full_name(full_name)
        if repository is None or not repository.enabled:
            return _error("unknown_repository", f"repository '{full_name}' is not indexed")
        try:
            return await container.code_use_cases.explain_structure(repository.id)
        except ApplicationError as exc:
            return await _code_error(exc)

    # -- engineering-intelligence tools ---------------------------------------------

    async def _resolve_enabled(full_name: str) -> Repository | dict[str, Any]:
        repository = await container.repositories.get_by_full_name(full_name)
        if repository is None or not repository.enabled:
            return _error("unknown_repository", f"repository '{full_name}' is not indexed")
        return repository

    @mcp.tool
    async def mnemosyne_get_repository_health(full_name: str) -> dict[str, Any]:
        """Health score (0-100), grade, component breakdown, and findings for a repository."""
        await auth()
        repo = await _resolve_enabled(full_name)
        if isinstance(repo, dict):
            return repo
        return _health_dict(full_name, await container.intelligence.health(repo.id))

    @mcp.tool
    async def mnemosyne_get_delivery_metrics(full_name: str) -> dict[str, Any]:
        """Delivery analytics: merge rate, median merge/resolution time, PR size distribution."""
        await auth()
        repo = await _resolve_enabled(full_name)
        if isinstance(repo, dict):
            return repo
        return {"full_name": full_name, **asdict(await container.intelligence.delivery(repo.id))}

    @mcp.tool
    async def mnemosyne_get_backlog_metrics(full_name: str) -> dict[str, Any]:
        """Backlog analytics: open/stale issues, open-to-closed ratio, oldest open age."""
        await auth()
        repo = await _resolve_enabled(full_name)
        if isinstance(repo, dict):
            return repo
        return {"full_name": full_name, **asdict(await container.intelligence.backlog(repo.id))}

    @mcp.tool
    async def mnemosyne_get_review_bottlenecks(full_name: str) -> dict[str, Any]:
        """Review bottlenecks: slow/absent-review PRs and reviewer-load concentration."""
        await auth()
        repo = await _resolve_enabled(full_name)
        if isinstance(repo, dict):
            return repo
        result = await container.intelligence.review_bottlenecks(repo.id)
        return {"full_name": full_name, **asdict(result)}

    @mcp.tool
    async def mnemosyne_get_maintenance_risk(full_name: str) -> dict[str, Any]:
        """Maintenance-risk level (low/medium/high) with the reasons that raised it."""
        await auth()
        repo = await _resolve_enabled(full_name)
        if isinstance(repo, dict):
            return repo
        result = await container.intelligence.maintenance_risk(repo.id)
        return {"full_name": full_name, **asdict(result)}

    @mcp.tool
    async def mnemosyne_get_portfolio_overview(
        organization: str | None = None,
    ) -> dict[str, Any]:
        """Cross-repo overview: health leaderboard, most-active, abandoned, bug-heavy repos.

        Pass `organization` (owner login) to scope the overview to one org; omit for
        all indexed repositories.
        """
        await auth()
        return asdict(await container.intelligence.portfolio(organization=organization))

    @mcp.tool
    async def mnemosyne_compare_repositories(full_names: list[str]) -> dict[str, Any]:
        """Compare repositories by health grade and key delivery metrics, side by side."""
        await auth()
        ids = []
        for name in full_names:
            repo = await _resolve_enabled(name)
            if isinstance(repo, dict):
                return repo
            ids.append(repo.id)
        return {"comparison": await container.intelligence.compare(ids)}

    @mcp.tool
    async def mnemosyne_generate_onboarding_summary(full_name: str) -> dict[str, Any]:
        """Newcomer brief: health, docs/OpenSpec presence, and top findings for a repository."""
        await auth()
        repo = await _resolve_enabled(full_name)
        if isinstance(repo, dict):
            return repo
        return await container.intelligence.onboarding_summary(repo.id)

    # -- PM/PO delivery tools -------------------------------------------------------

    async def _delivery_call(full_name: str, method: str) -> dict[str, Any]:
        await auth()
        repo = await _resolve_enabled(full_name)
        if isinstance(repo, dict):
            return repo
        result = await getattr(container.delivery_intelligence, method)(repo.id)
        return {"full_name": full_name, **asdict(result)}

    @mcp.tool
    async def mnemosyne_get_flow_metrics(full_name: str) -> dict[str, Any]:
        """Flow: cycle/lead-time percentiles (p50/p85/p95), WIP, aging, untriaged backlog."""
        return await _delivery_call(full_name, "flow")

    @mcp.tool
    async def mnemosyne_get_throughput_trend(full_name: str) -> dict[str, Any]:
        """Throughput and net-flow over the metrics time-series (needs accrued history)."""
        return await _delivery_call(full_name, "throughput")

    @mcp.tool
    async def mnemosyne_get_backlog_forecast(full_name: str) -> dict[str, Any]:
        """Projected backlog-clear date from the trailing close rate (or why there is none)."""
        return await _delivery_call(full_name, "forecast")

    @mcp.tool
    async def mnemosyne_get_work_mix(full_name: str) -> dict[str, Any]:
        """Work-mix: feature / bug / tech-debt / docs distribution and the bug ratio."""
        return await _delivery_call(full_name, "work_mix")

    @mcp.tool
    async def mnemosyne_get_quality_signals(full_name: str) -> dict[str, Any]:
        """Quality: bug ratio, reopened-issue rate, and time-to-first-response percentiles."""
        return await _delivery_call(full_name, "quality")

    @mcp.tool
    async def mnemosyne_get_team_load(full_name: str) -> dict[str, Any]:
        """Team load per assignee, reviewer load, and bus-factor risk (no per-person ranking)."""
        return await _delivery_call(full_name, "team_load")

    @mcp.tool
    async def mnemosyne_get_milestone_progress(full_name: str) -> dict[str, Any]:
        """Per-milestone percent complete and projected completion vs. due date."""
        await auth()
        repo = await _resolve_enabled(full_name)
        if isinstance(repo, dict):
            return repo
        result = await container.delivery_intelligence.milestones(repo.id)
        return {"full_name": full_name, "milestones": [asdict(m) for m in result]}

    @mcp.tool
    async def mnemosyne_get_delivery_scorecard(
        organization: str | None = None,
    ) -> dict[str, Any]:
        """Portfolio delivery scorecard: predictability, throughput direction, backlog, risk.

        Pass `organization` (owner login) to scope to one org; omit for all repos.
        """
        await auth()
        board = await container.delivery_intelligence.delivery_scorecard(
            organization=organization
        )
        return {"scorecard": [asdict(e) for e in board]}

    @mcp.tool
    async def mnemosyne_get_organization_intelligence(organization: str) -> dict[str, Any]:
        """One-call health + delivery rollup for an organization.

        Aggregates the org's repositories: count, scored count, average/median health,
        grade distribution, at-risk milestone total, throughput directions, and the
        most-active / abandoned / bug-heavy lists — so an agent can answer "how is this
        org doing overall?" without looping every repository.
        """
        await auth()
        portfolio = await container.intelligence.portfolio(organization=organization)
        scorecard = await container.delivery_intelligence.delivery_scorecard(
            organization=organization
        )
        return build_org_intelligence(organization, portfolio, scorecard)

    # -- cross-repo tools ------------------------------------------------------

    @mcp.tool
    async def mnemosyne_find_repositories(
        query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Fuzzy-find indexed repositories by name/description/language.

        Use this to resolve a vague reference (e.g. "the auth repo") into the exact
        `owner/name` other tools expect, when you don't already know it.
        """
        await auth()
        return await container.cross_repo.find_repositories(query, limit=limit)

    @mcp.tool
    async def mnemosyne_get_repository_metrics(full_name: str) -> dict[str, Any]:
        """Raw computed metrics snapshot for a repository (issue/PR/doc counts, cycle
        times, label breakdowns) — the unscored inputs behind the health/delivery tools."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        metrics = await container.metrics_store.get(repository.id)
        if metrics is None:
            return _error(
                "no_metrics", f"repository '{full_name}' has no computed metrics yet"
            )
        return {"full_name": str(repository.full_name), "metrics": metrics}

    @mcp.tool
    async def mnemosyne_find_stale_issues_across_repos(
        organization: str | None = None, threshold_days: int = 30, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Open issues with no activity beyond the threshold, across all indexed repos
        (or one `organization`), oldest first — portfolio-wide triage in one call."""
        await auth()
        return await container.cross_repo.find_stale_issues(
            organization=organization, threshold_days=threshold_days, limit=limit
        )

    @mcp.tool
    async def mnemosyne_find_stale_prs_across_repos(
        organization: str | None = None, threshold_days: int = 30, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Open pull requests with no activity beyond the threshold, across all indexed
        repos (or one `organization`), oldest first."""
        await auth()
        return await container.cross_repo.find_stale_prs(
            organization=organization, threshold_days=threshold_days, limit=limit
        )

    @mcp.tool
    async def mnemosyne_get_recent_activity(
        organization: str | None = None, limit: int = 15
    ) -> dict[str, Any]:
        """Recent cross-repo activity: most recently synced repositories plus the latest
        updated issues and pull requests (all indexed repos, or one `organization`)."""
        await auth()
        return await container.cross_repo.recent_activity(
            organization=organization, limit=limit
        )

    @mcp.tool
    async def mnemosyne_search_all(
        query: str, kind: str = "docs", organization: str | None = None, limit: int = 8
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Search across many repositories at once (not one repo). kind: docs | code | issues.

        docs/code are semantic; issues are keyword-ranked. Scope to one `organization`
        or omit for all indexed repos. Each result carries its repository `full_name`.
        """
        await auth()
        try:
            return await container.cross_repo.search(
                query, kind=kind, organization=organization, limit=limit
            )
        except ValueError as exc:
            return _error("invalid_kind", str(exc))

    # -- capability / feature composites (PM/PO one-call answers) --------------

    @mcp.tool
    async def mnemosyne_get_repository_capabilities(full_name: str) -> dict[str, Any]:
        """What a project does, in one call: capabilities (OpenSpec spec areas),
        documentation topics, open/closed issue counts, **bug count**, and PR counts.

        Answers PM/PO questions like "which capabilities does this project have?" and
        "how many bugs does it have?" without several tool calls.
        """
        await auth()
        try:
            return await container.capabilities.repository_capabilities(full_name)
        except ApplicationError as exc:
            return _error("unknown_repository", str(exc))

    @mcp.tool
    async def mnemosyne_get_organization_capabilities(organization: str) -> dict[str, Any]:
        """What an organization can do right now: the union of capabilities across its
        indexed repositories, total open bugs, and a per-project capability brief."""
        await auth()
        return await container.capabilities.organization_capabilities(organization)

    @mcp.tool
    async def mnemosyne_list_repositories_with_openspec(
        organization: str,
    ) -> list[dict[str, Any]]:
        """Indexed repositories in an organization that have OpenSpec (per the latest sync)."""
        await auth()
        coverage = await container.capabilities.organization_openspec_coverage(organization)
        rows: list[dict[str, Any]] = coverage["with_openspec"]
        return rows

    @mcp.tool
    async def mnemosyne_list_repositories_missing_openspec(
        organization: str,
    ) -> list[dict[str, Any]]:
        """Indexed repositories in an organization with no OpenSpec detected (adoption targets)."""
        await auth()
        coverage = await container.capabilities.organization_openspec_coverage(organization)
        rows: list[dict[str, Any]] = coverage["without_openspec"]
        return rows

    @mcp.tool
    async def mnemosyne_get_repository_readiness(full_name: str) -> dict[str, Any]:
        """Classify a repository as MVP / READY / DONE from observable signals (CI, tests,
        OpenSpec/ADRs, issues/PRs, docs, dependency hygiene, security scanning), with a
        per-check met/missing/unknown breakdown. 'unknown' means the signal needs a
        code-indexing mode (file tree) to detect."""
        await auth()
        try:
            return await container.readiness.repository_readiness(full_name)
        except ApplicationError as exc:
            return _error("unknown_repository", str(exc))

    @mcp.tool
    async def mnemosyne_get_organization_readiness(organization: str) -> dict[str, Any]:
        """Readiness distribution (MVP/READY/DONE counts) for an organization plus each
        repository's gate and what it's missing to reach READY."""
        await auth()
        return await container.readiness.organization_readiness(organization)

    @mcp.tool
    async def mnemosyne_get_readiness_history(full_name: str) -> dict[str, Any]:
        """A repository's readiness-gate trend over time (dated MVP/READY/DONE points),
        recorded daily. Empty until the daily job has run at least once."""
        await auth()
        try:
            return await container.readiness.repository_history(full_name)
        except ApplicationError as exc:
            return _error("unknown_repository", str(exc))

    @mcp.tool
    async def mnemosyne_get_readiness_regressions(organization: str) -> dict[str, Any]:
        """Repositories in an organization whose latest readiness gate dropped below the
        previous recorded gate (e.g. READY->MVP), with from/to gate and the date."""
        await auth()
        return await container.readiness.organization_regressions(organization)

    @mcp.tool
    async def mnemosyne_get_organization_vulnerabilities(organization: str) -> dict[str, Any]:
        """Repositories in an organization with open critical/high Dependabot alerts,
        most-critical first, plus org totals. Captured during sync (best-effort — needs a
        credential with security-alerts read; repos without the signal are omitted)."""
        await auth()
        return await container.security.organization_vulnerabilities(organization)

    @mcp.tool
    async def mnemosyne_get_organization_digest(organization: str) -> dict[str, Any]:
        """One-call attention digest for an organization: readiness regressions, oldest
        stale issues/PRs, at-risk milestone count, and a human-readable summary line."""
        await auth()
        return await container.digest.build(organization)

    @mcp.tool
    async def mnemosyne_remember(
        content: str,
        full_name: str | None = None,
        organization: str | None = None,
        kind: str = "note",
    ) -> dict[str, Any]:
        """Persist a durable memory (learning/decision/gotcha/convention/todo) scoped to a
        repository (full_name) or an organization, recalled later by any agent. Writes only
        to Mnemosyne, never to GitHub. Provide exactly one of full_name or organization."""
        caller = await auth()
        try:
            if full_name:
                return await container.memory.remember_repository(
                    full_name, content=content, kind=kind, author=caller.subject)
            if organization:
                return await container.memory.remember_organization(
                    organization, content=content, kind=kind, author=caller.subject)
            return _error("invalid_request", "provide full_name or organization")
        except ApplicationError as exc:
            return _error("unknown_repository", str(exc))

    @mcp.tool
    async def mnemosyne_recall(
        full_name: str | None = None,
        organization: str | None = None,
        query: str | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Recall memories for a repository (full_name) or organization, newest first,
        optionally filtered by a text query and/or kind."""
        await auth()
        try:
            if full_name:
                return await container.memory.recall_repository(
                    full_name, query=query, kind=kind, limit=limit)
            if organization:
                return await container.memory.recall_organization(
                    organization, query=query, kind=kind, limit=limit)
            return _error("invalid_request", "provide full_name or organization")
        except ApplicationError as exc:
            return _error("unknown_repository", str(exc))

    @mcp.tool
    async def mnemosyne_forget(memory_id: str) -> dict[str, Any]:
        """Delete a memory by id. Returns {deleted: bool}."""
        await auth()
        from uuid import UUID
        try:
            deleted = await container.memory.forget(UUID(memory_id))
        except ValueError:
            return _error("invalid_request", "memory_id must be a UUID")
        return {"deleted": deleted}

    @mcp.tool
    async def mnemosyne_generate_feature_document(full_name: str) -> dict[str, Any]:
        """Generate a Markdown document of the project's features/capabilities, grounded
        in indexed docs/OpenSpec/code (with citations). For "write up everything this
        project does"."""
        await auth()
        repository = await _resolve_repo(full_name)
        if isinstance(repository, dict):
            return repository
        result = await container.context_use_cases.ask(
            repository.id, FEATURE_DOCUMENT_PROMPT
        )
        return {"full_name": str(repository.full_name), "document": result["answer"],
                "sources": result["sources"], "grounded": result["grounded"]}

    return mcp


def _health_dict(full_name: str, health: Any) -> dict[str, Any]:
    return {
        "full_name": full_name,
        "has_data": health.has_data,
        "overall": health.overall,
        "grade": health.grade.value if health.grade else None,
        "components": [
            {"name": c.name, "weight": c.weight, "score": c.score, "inputs": c.inputs}
            for c in health.components
        ],
        "findings": [
            {"severity": f.severity.value, "message": f.message, "metric": f.metric}
            for f in health.findings
        ],
    }


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
