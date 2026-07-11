"""SyncRepository orchestrator (spec: repository-sync; design D6-D8).

Runs the planned steps for a repository's indexing mode, records
per-step progress, honors ignore rules and secret quarantine, and
recomputes metrics at the end. Idempotent: re-syncs upsert by natural
keys and skip unchanged documents by content hash.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.application.errors import SyncAlreadyRunningError, UnknownResourceError
from app.application.metrics_recompute import (
    MetricsHistoryProtocol,
    MetricsRecomputeService,
)
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.domain.entities.document import Document
from app.domain.entities.issue import Issue
from app.domain.entities.milestone import Milestone
from app.domain.entities.openspec_change import OpenSpecChange
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.entities.source_chunk import SourceChunk
from app.domain.entities.source_file import SourceFile
from app.domain.entities.sync_job import SyncJob
from app.domain.ports.code_chunker_port import CodeChunkerPort
from app.domain.ports.github_port import GitHubFileData, GitHubNotFoundError, GitHubPort
from app.domain.ports.infra_ports import (
    EmbeddableChunk,
    EmbeddingPort,
    ObjectStoragePort,
    SyncLockPort,
)
from app.domain.ports.persistence_ports import (
    DocumentPort,
    FilePort,
    IssuePort,
    MilestonePort,
    OpenSpecPort,
    PullRequestPort,
    RepositoryPort,
    SourceChunkPort,
    SyncJobPort,
)
from app.domain.services.document_classifier import (
    classify_document,
    document_title,
    is_documentation_path,
)
from app.domain.services.file_importance import (
    classify_importance,
    detect_language,
    file_extension,
)
from app.domain.services.issue_metrics import IssueMetricsService
from app.domain.services.openspec_parser import (
    find_change_folders,
    interesting_files,
    parse_change,
)
from app.domain.services.path_policy import IGNORE_FILE_NAME, PathPolicy
from app.domain.services.pr_metrics import PullRequestMetricsService
from app.domain.services.secret_scanner import has_secrets
from app.domain.value_objects.enums import (
    EmbeddingStatus,
    IssueState,
    OpenSpecStatus,
    PullRequestState,
    SyncStatus,
    SyncStep,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MetricsWriter:
    """Persists computed metrics + summary (task 5.3). Backed by Postgres adapter."""

    store: object  # PostgresMetricsRepository-compatible

    async def write(
        self,
        repository_id: UUID,
        issue_metrics: dict[str, Any],
        pr_metrics: dict[str, Any],
        summary: dict[str, Any],
        at: datetime,
    ) -> None:
        await self.store.save(  # type: ignore[attr-defined]
            repository_id,
            issue_metrics=issue_metrics,
            pr_metrics=pr_metrics,
            summary=summary,
            computed_at=at,
        )


class SyncRepositoryUseCase:
    def __init__(
        self,
        repositories: RepositoryPort,
        documents: DocumentPort,
        openspec: OpenSpecPort,
        issues: IssuePort,
        pull_requests: PullRequestPort,
        files: FilePort,
        sync_jobs: SyncJobPort,
        github: GitHubPort,
        connection_use_cases: GitHubConnectionUseCases,
        sync_lock: SyncLockPort,
        storage: ObjectStoragePort,
        embeddings: EmbeddingPort,
        metrics_writer: MetricsWriter,
        source_chunks: SourceChunkPort,
        code_chunker: CodeChunkerPort,
        milestones: "MilestonePort | None" = None,
        metrics_history: "MetricsHistoryProtocol | None" = None,
        issue_metrics_service: IssueMetricsService | None = None,
        pr_metrics_service: PullRequestMetricsService | None = None,
        source_size_cap: int = 512 * 1024,
    ) -> None:
        self._repositories = repositories
        self._documents = documents
        self._openspec = openspec
        self._issues = issues
        self._pull_requests = pull_requests
        self._files = files
        self._sync_jobs = sync_jobs
        self._github = github
        self._connections = connection_use_cases
        self._sync_lock = sync_lock
        self._storage = storage
        self._embeddings = embeddings
        self._metrics_writer = metrics_writer
        self._source_chunks = source_chunks
        self._code_chunker = code_chunker
        self._milestones = milestones
        self._metrics_history = metrics_history
        self._source_size_cap = source_size_cap
        self._issue_metrics = issue_metrics_service or IssueMetricsService()
        self._pr_metrics = pr_metrics_service or PullRequestMetricsService()

    async def run(self, repository_id: UUID, job_id: UUID) -> SyncJob:
        repository = await self._repositories.get(repository_id)
        if repository is None:
            raise UnknownResourceError(f"repository {repository_id} not found")
        job = await self._sync_jobs.get(job_id)
        if job is None:
            raise UnknownResourceError(f"sync job {job_id} not found")

        if not await self._sync_lock.acquire(repository_id):
            raise SyncAlreadyRunningError(str(repository.full_name))
        try:
            return await self._run_locked(repository, job)
        finally:
            await self._sync_lock.release(repository_id)

    async def _run_locked(self, repository: Repository, job: SyncJob) -> SyncJob:
        now = datetime.now(UTC)
        job.start(now)
        await self._sync_jobs.save(job)

        token = await self._connections.credential_for(repository.connection_id)
        full_name = str(repository.full_name)
        context = _SyncContext(repository=repository, token=token, full_name=full_name)

        handlers = {
            SyncStep.METADATA: self._sync_metadata,
            SyncStep.DOCS: self._sync_docs,
            SyncStep.OPENSPEC: self._sync_openspec,
            SyncStep.ISSUES: self._sync_issues,
            SyncStep.PULL_REQUESTS: self._sync_pull_requests,
            SyncStep.FILE_TREE: self._sync_file_tree,
            SyncStep.SOURCE_CODE: self._sync_source_code,
            SyncStep.EMBEDDINGS: self._sync_embeddings,
            SyncStep.METRICS: self._sync_metrics,
        }
        for step_result in job.steps:
            step = step_result.step
            try:
                items = await handlers[step](context)
                job.record_step(step, SyncStatus.SUCCEEDED, items=items)
            except Exception as exc:
                logger.exception("sync step %s failed for %s", step, full_name)
                job.record_step(step, SyncStatus.FAILED, error=str(exc)[:500])
            await self._sync_jobs.save(job)

        job.finish(datetime.now(UTC))
        await self._sync_jobs.save(job)

        # Advance last_synced_at whenever the essential steps succeeded — a
        # degraded job (best-effort step failed) still delivered core data.
        if job.essential_succeeded:
            repository.last_synced_at = job.finished_at
            await self._repositories.save(repository)
        return job

    # -- steps ---------------------------------------------------------------

    async def _sync_metadata(self, ctx: "_SyncContext") -> int:
        data = await self._github.get_repository(ctx.token, ctx.full_name)
        ctx.repository.description = data.description
        ctx.repository.default_branch = data.default_branch
        ctx.repository.primary_language = data.primary_language
        ctx.repository.archived = data.archived
        ctx.repository.github_updated_at = data.updated_at
        await self._repositories.save(ctx.repository)
        return 1

    async def _load_tree_paths(self, ctx: "_SyncContext") -> list[str]:
        if ctx.tree is None:
            ctx.tree = await self._github.get_tree(
                ctx.token, ctx.full_name, ctx.repository.default_branch
            )
        return [f.path for f in ctx.tree]

    async def _load_policy(self, ctx: "_SyncContext") -> PathPolicy:
        if ctx.policy is None:
            paths = await self._load_tree_paths(ctx)
            content = None
            if IGNORE_FILE_NAME in paths:
                content = await self._github.get_file_content(
                    ctx.token, ctx.full_name, IGNORE_FILE_NAME
                )
            ctx.policy = PathPolicy.from_ignore_file(content)
        return ctx.policy

    async def _capture_document(self, ctx: "_SyncContext", path: str) -> Document | None:
        try:
            content = await self._github.get_file_content(ctx.token, ctx.full_name, path)
        except GitHubNotFoundError:
            return None
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        existing = await self._documents.get_by_path(ctx.repository.id, path)
        if existing is not None and existing.content_hash == content_hash:
            return existing  # unchanged: no rewrite, no re-embed (spec)

        quarantined = has_secrets(content)
        document = Document(
            id=uuid4(),
            repository_id=ctx.repository.id,
            path=path,
            type=classify_document(path),
            title=document_title(path, content),
            content=None if quarantined else content,
            content_hash=content_hash,
            last_commit_sha=next((f.sha for f in ctx.tree or [] if f.path == path), None),
            quarantined=quarantined,
            embedding_status=EmbeddingStatus.SKIPPED if quarantined else EmbeddingStatus.PENDING,
            captured_at=datetime.now(UTC),
        )
        await self._documents.save(document)
        return document

    async def _sync_docs(self, ctx: "_SyncContext") -> int:
        paths = await self._load_tree_paths(ctx)
        policy = await self._load_policy(ctx)
        doc_paths = [p for p in paths if is_documentation_path(p) and not policy.is_ignored(p)]
        captured = 0
        for path in doc_paths:
            if await self._capture_document(ctx, path) is not None:
                captured += 1
        await self._documents.delete_missing(ctx.repository.id, set(doc_paths))
        return captured

    async def _sync_openspec(self, ctx: "_SyncContext") -> int:
        paths = await self._load_tree_paths(ctx)
        policy = await self._load_policy(ctx)
        folders = find_change_folders(policy.filter(paths))
        count = 0
        for folder, change_id in folders.items():
            contents: dict[str, str] = {}
            for path in interesting_files(folder):
                if path in paths:
                    try:
                        contents[path] = await self._github.get_file_content(
                            ctx.token, ctx.full_name, path
                        )
                    except GitHubNotFoundError:
                        continue
            parsed = parse_change(folder, change_id, paths, contents)
            await self._openspec.save(
                OpenSpecChange(
                    id=uuid4(),
                    repository_id=ctx.repository.id,
                    change_id=parsed.change_id,
                    path=parsed.path,
                    status=OpenSpecStatus(parsed.status),
                    proposal=parsed.proposal,
                    design=parsed.design,
                    tasks=parsed.tasks,
                    affected_specs=parsed.affected_specs,
                    content_hash=parsed.content_hash,
                )
            )
            count += 1
        return count

    async def _sync_issues(self, ctx: "_SyncContext") -> int:
        raw = await self._github.list_issues(ctx.token, ctx.full_name)
        issues = [
            Issue(
                id=uuid4(),
                repository_id=ctx.repository.id,
                github_issue_id=i.github_id,
                number=i.number,
                title=i.title,
                body=i.body,
                state=IssueState(i.state),
                author=i.author,
                labels=i.labels,
                assignees=i.assignees,
                milestone=i.milestone,
                created_at=i.created_at,
                updated_at=i.updated_at,
                closed_at=i.closed_at,
                comments_count=i.comments_count,
            )
            for i in raw
            if not i.is_pull_request  # PRs are never stored as issues (spec)
        ]
        await self._issues.save_many(issues)
        await self._sync_milestones(ctx)
        return len(issues)

    async def _sync_milestones(self, ctx: "_SyncContext") -> None:
        if self._milestones is None:
            return
        raw = await self._github.list_milestones(ctx.token, ctx.full_name)
        await self._milestones.replace_for_repository(
            ctx.repository.id,
            [
                Milestone(
                    id=uuid4(),
                    repository_id=ctx.repository.id,
                    number=m.number,
                    title=m.title,
                    state=m.state,
                    due_on=m.due_on,
                    open_issues=m.open_issues,
                    closed_issues=m.closed_issues,
                    updated_at=m.updated_at,
                )
                for m in raw
            ],
        )

    async def _sync_pull_requests(self, ctx: "_SyncContext") -> int:
        raw = await self._github.list_pull_requests(ctx.token, ctx.full_name)
        prs = [
            PullRequest(
                id=uuid4(),
                repository_id=ctx.repository.id,
                github_pr_id=p.github_id,
                number=p.number,
                title=p.title,
                body=p.body,
                state=PullRequestState(p.state),
                merged=p.merged,
                author=p.author,
                reviewers=p.reviewers,
                created_at=p.created_at,
                updated_at=p.updated_at,
                closed_at=p.closed_at,
                merged_at=p.merged_at,
                first_review_at=p.first_review_at,
                changed_files=p.changed_files,
                additions=p.additions,
                deletions=p.deletions,
                review_decision=p.review_decision,
            )
            for p in raw
        ]
        await self._pull_requests.save_many(prs)
        return len(prs)

    async def _sync_file_tree(self, ctx: "_SyncContext") -> int:
        if ctx.tree is None:
            await self._load_tree_paths(ctx)
        policy = await self._load_policy(ctx)
        now = datetime.now(UTC)
        files = [
            SourceFile(
                id=uuid4(),
                repository_id=ctx.repository.id,
                path=f.path,
                extension=file_extension(f.path),
                language=detect_language(f.path),
                size_bytes=f.size,
                sha=f.sha,
                is_binary=f.is_binary,
                is_important=classify_importance(f.path) is not None,
                important_kind=classify_importance(f.path),
                last_seen_at=now,
            )
            for f in ctx.tree or []
            if not policy.is_ignored(f.path)
        ]
        await self._files.replace_tree(ctx.repository.id, files)
        return len(files)

    async def _sync_source_code(self, ctx: "_SyncContext") -> int:
        """Capture, chunk, and embed authorized source content (spec: code-context)."""
        policy = await self._load_policy(ctx)
        files = await self._files.list_by_repository(ctx.repository.id)
        captured = 0
        for file in files:
            if file.is_binary or policy.is_ignored(file.path):
                continue
            if file.size_bytes > self._source_size_cap:
                continue
            try:
                content = await self._github.get_file_content(
                    ctx.token, ctx.full_name, file.path
                )
            except GitHubNotFoundError:
                continue
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            if file.content_captured and file.content_hash == content_hash:
                continue  # unchanged: no re-chunk / re-embed (spec)

            if has_secrets(content):
                file.quarantined = True
                file.content = None
                file.content_captured = False
                file.content_hash = content_hash
                await self._files.save_content(file)
                await self._source_chunks.delete_for_file(file.id)
                continue

            file.content = content
            file.content_captured = True
            file.quarantined = False
            file.content_hash = content_hash
            await self._files.save_content(file)

            chunks = [
                SourceChunk(
                    id=uuid4(),
                    file_id=file.id,
                    repository_id=ctx.repository.id,
                    chunk_type=c.chunk_type,
                    symbol_name=c.symbol_name,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    content=c.content,
                    content_hash=hashlib.sha256(c.content.encode()).hexdigest(),
                )
                for c in self._code_chunker.chunk(file.path, content, file.language)
            ]
            await self._source_chunks.replace_for_file(file.id, chunks)
            await self._embeddings.embed_source_chunks(
                ctx.repository.id,
                [EmbeddableChunk(chunk_id=c.id, text=c.content) for c in chunks],
            )
            captured += 1
        return captured

    async def _sync_embeddings(self, ctx: "_SyncContext") -> int:
        documents = await self._documents.list_by_repository(ctx.repository.id)
        embedded = 0
        for document in documents:
            if document.embedding_status is not EmbeddingStatus.PENDING or not document.embeddable:
                continue
            chunks = _chunk_markdown(document.content or "")
            await self._embeddings.embed_document(document.id, ctx.repository.id, chunks)
            document.embedding_status = EmbeddingStatus.EMBEDDED
            await self._documents.save(document)
            embedded += 1
        return embedded

    async def _sync_metrics(self, ctx: "_SyncContext") -> int:
        service = MetricsRecomputeService(
            self._issues,
            self._pull_requests,
            self._documents,
            self._openspec,
            self._metrics_writer.store,  # type: ignore[arg-type]
            self._issue_metrics,
            self._pr_metrics,
            history=self._metrics_history,
        )
        # Best-effort: a releases-check hiccup must not fail the essential metrics
        # step. None makes recompute preserve the last captured value.
        try:
            has_releases: bool | None = await self._github.has_releases(
                ctx.token, ctx.full_name
            )
        except Exception:
            logger.warning("releases check failed for %s", ctx.full_name)
            has_releases = None
        try:
            vulnerabilities = await self._github.vulnerability_summary(
                ctx.token, ctx.full_name
            )
        except Exception:
            logger.warning("vulnerability check failed for %s", ctx.full_name)
            vulnerabilities = None
        await service.recompute(
            ctx.repository, has_releases=has_releases, vulnerabilities=vulnerabilities
        )
        return 1


@dataclass(slots=True)
class _SyncContext:
    repository: Repository
    token: str
    full_name: str
    tree: list[GitHubFileData] | None = None
    policy: PathPolicy | None = None


def _metrics_dict(metrics: Any) -> dict[str, Any]:
    from dataclasses import asdict

    return dict(asdict(metrics))


def _chunk_markdown(content: str, max_chars: int = 6000) -> list[str]:
    """Heading-bounded chunks, split further if oversized (design D7)."""
    sections: list[str] = []
    current: list[str] = []
    for line in content.splitlines():
        if line.startswith(("# ", "## ")) and current:
            sections.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        sections.append("\n".join(current))

    chunks: list[str] = []
    for section in sections:
        text = section.strip()
        if not text:
            continue
        while len(text) > max_chars:
            chunks.append(text[:max_chars])
            text = text[max_chars:]
        if text:
            chunks.append(text)
    return chunks
