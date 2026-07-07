"""Domain/application -> API schema mapping and error translation."""

from dataclasses import asdict

from app.application.errors import (
    ApplicationError,
    InvalidCredentialError,
    MissingPermissionsError,
    RepositoryNotSyncedError,
    SyncAlreadyRunningError,
    UnknownResourceError,
)
from app.domain.entities.context_pack import ContextPack
from app.domain.entities.document import Document
from app.domain.entities.issue import Issue
from app.domain.entities.openspec_change import OpenSpecChange
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.entities.source_file import SourceFile
from app.domain.entities.sync_job import SyncJob
from app.interfaces.api.errors import ApiError, ConflictError, NotFoundError
from app.interfaces.api.schemas.schemas import (
    ContextPackResponse,
    DocumentResponse,
    DocumentSummaryResponse,
    IssueResponse,
    OpenSpecChangeResponse,
    PullRequestResponse,
    RepositoryResponse,
    SourceFileResponse,
    SyncJobResponse,
    SyncStepResponse,
)


def translate_error(exc: ApplicationError) -> ApiError:
    """Application error -> HTTP error (spec: rest-api status mapping)."""
    if isinstance(exc, UnknownResourceError):
        return NotFoundError(str(exc))
    if isinstance(exc, SyncAlreadyRunningError):
        return ConflictError(f"a sync is already running for {exc}", code="sync_already_running")
    if isinstance(exc, RepositoryNotSyncedError):
        return ConflictError(str(exc), code="repository_not_synced")
    if isinstance(exc, MissingPermissionsError):
        return ApiError(str(exc), code="missing_permissions", status_code=400)
    if isinstance(exc, InvalidCredentialError):
        return ApiError(str(exc), code="invalid_credential", status_code=400)
    return ApiError(str(exc), code="application_error", status_code=400)


def repository_response(repo: Repository) -> RepositoryResponse:
    return RepositoryResponse(
        id=repo.id,
        full_name=str(repo.full_name),
        description=repo.description,
        visibility=repo.visibility.value,
        default_branch=repo.default_branch,
        primary_language=repo.primary_language,
        archived=repo.archived,
        enabled=repo.enabled,
        indexing_mode=repo.indexing_mode.value,
        last_synced_at=repo.last_synced_at,
    )


def sync_job_response(job: SyncJob) -> SyncJobResponse:
    return SyncJobResponse(
        id=job.id,
        repository_id=job.repository_id,
        mode=job.mode.value,
        status=job.status.value,
        steps=[
            SyncStepResponse(
                step=s.step.value,
                status=s.status.value,
                error=s.error,
                items_processed=s.items_processed,
            )
            for s in job.steps
        ],
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def document_summary_response(doc: Document) -> DocumentSummaryResponse:
    return DocumentSummaryResponse(
        id=doc.id,
        path=doc.path,
        type=doc.type.value,
        title=doc.title,
        quarantined=doc.quarantined,
        captured_at=doc.captured_at,
    )


def document_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        **document_summary_response(doc).model_dump(),
        content=doc.content,
    )


def openspec_response(change: OpenSpecChange) -> OpenSpecChangeResponse:
    return OpenSpecChangeResponse(
        change_id=change.change_id,
        path=change.path,
        status=change.status.value,
        proposal=change.proposal,
        design=change.design,
        tasks=change.tasks,
        affected_specs=change.affected_specs,
    )


def issue_response(issue: Issue) -> IssueResponse:
    return IssueResponse(
        number=issue.number,
        title=issue.title,
        state=issue.state.value,
        author=issue.author,
        labels=issue.labels,
        assignees=issue.assignees,
        created_at=issue.created_at,
        closed_at=issue.closed_at,
        resolution_time_seconds=issue.resolution_time_seconds,
        comments_count=issue.comments_count,
    )


def pull_request_response(pr: PullRequest) -> PullRequestResponse:
    return PullRequestResponse(
        number=pr.number,
        title=pr.title,
        state=pr.state.value,
        merged=pr.merged,
        author=pr.author,
        reviewers=pr.reviewers,
        created_at=pr.created_at,
        merged_at=pr.merged_at,
        time_to_merge_seconds=pr.time_to_merge_seconds,
        time_to_first_review_seconds=pr.time_to_first_review_seconds,
        additions=pr.additions,
        deletions=pr.deletions,
    )


def source_file_response(f: SourceFile) -> SourceFileResponse:
    return SourceFileResponse(
        path=f.path,
        extension=f.extension,
        language=f.language,
        size_bytes=f.size_bytes,
        is_binary=f.is_binary,
        is_important=f.is_important,
        important_kind=f.important_kind,
    )


def context_pack_response(pack: ContextPack) -> ContextPackResponse:
    return ContextPackResponse(
        id=pack.id,
        repository_id=pack.repository_id,
        query=pack.query,
        mode=pack.mode.value,
        repository_summary=pack.repository_summary,
        relevant_docs=[asdict(d) for d in pack.relevant_docs],
        relevant_openspec_changes=[asdict(o) for o in pack.relevant_openspec_changes],
        relevant_issues=[asdict(i) for i in pack.relevant_issues],
        relevant_pull_requests=[asdict(p) for p in pack.relevant_pull_requests],
        relevant_files=[asdict(f) for f in pack.relevant_files],
        risks=pack.risks,
        suggested_next_steps=pack.suggested_next_steps,
        excluded_categories=pack.excluded_categories,
        sync_timestamp=pack.sync_timestamp,
        created_at=pack.created_at,
    )
