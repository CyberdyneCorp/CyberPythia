"""Row <-> domain entity mapping."""

from app.domain.entities.audit_record import AuditRecord
from app.domain.entities.document import Document
from app.domain.entities.github_connection import GitHubConnection
from app.domain.entities.issue import Issue
from app.domain.entities.openspec_change import OpenSpecChange
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.entities.source_file import SourceFile
from app.domain.entities.sync_job import SyncJob, SyncStepResult
from app.domain.value_objects.enums import (
    ConnectionStatus,
    DocumentType,
    EmbeddingStatus,
    IndexingMode,
    IssueState,
    OpenSpecStatus,
    PullRequestState,
    RepositoryVisibility,
    SyncStatus,
    SyncStep,
)
from app.domain.value_objects.full_name import RepositoryFullName
from app.infrastructure.persistence.models import (
    AuditLogRow,
    DocumentRow,
    GitHubConnectionRow,
    IssueRow,
    OpenSpecChangeRow,
    PullRequestRow,
    RepositoryRow,
    SourceFileRow,
    SyncJobRow,
)


def connection_to_entity(row: GitHubConnectionRow) -> GitHubConnection:
    return GitHubConnection(
        id=row.id,
        owner=row.owner,
        owner_type=row.owner_type,
        encrypted_token=row.encrypted_token,
        token_hint=row.token_hint,
        permissions=list(row.permissions or []),
        status=ConnectionStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def connection_update_row(row: GitHubConnectionRow, entity: GitHubConnection) -> None:
    row.owner = entity.owner
    row.owner_type = entity.owner_type
    row.encrypted_token = entity.encrypted_token
    row.token_hint = entity.token_hint
    row.permissions = list(entity.permissions)
    row.status = entity.status.value
    row.created_at = entity.created_at  # type: ignore[assignment]
    row.updated_at = entity.updated_at  # type: ignore[assignment]


def repository_to_entity(row: RepositoryRow) -> Repository:
    return Repository(
        id=row.id,
        connection_id=row.connection_id,
        github_id=row.github_id,
        full_name=RepositoryFullName(row.full_name),
        description=row.description,
        visibility=RepositoryVisibility(row.visibility),
        default_branch=row.default_branch,
        primary_language=row.primary_language,
        archived=row.archived,
        github_updated_at=row.github_updated_at,
        enabled=row.enabled,
        indexing_mode=IndexingMode(row.indexing_mode),
        last_synced_at=row.last_synced_at,
    )


def repository_update_row(row: RepositoryRow, entity: Repository) -> None:
    row.connection_id = entity.connection_id
    row.github_id = entity.github_id
    row.full_name = str(entity.full_name)
    row.description = entity.description
    row.visibility = entity.visibility.value
    row.default_branch = entity.default_branch
    row.primary_language = entity.primary_language
    row.archived = entity.archived
    row.github_updated_at = entity.github_updated_at
    row.enabled = entity.enabled
    row.indexing_mode = entity.indexing_mode.value
    row.last_synced_at = entity.last_synced_at


def document_to_entity(row: DocumentRow) -> Document:
    return Document(
        id=row.id,
        repository_id=row.repository_id,
        path=row.path,
        type=DocumentType(row.type),
        title=row.title,
        content=row.content,
        content_hash=row.content_hash,
        last_commit_sha=row.last_commit_sha,
        quarantined=row.quarantined,
        embedding_status=EmbeddingStatus(row.embedding_status),
        captured_at=row.captured_at,
    )


def document_update_row(row: DocumentRow, entity: Document) -> None:
    row.repository_id = entity.repository_id
    row.path = entity.path
    row.type = entity.type.value
    row.title = entity.title
    row.content = entity.content
    row.content_hash = entity.content_hash
    row.last_commit_sha = entity.last_commit_sha
    row.quarantined = entity.quarantined
    row.embedding_status = entity.embedding_status.value
    row.captured_at = entity.captured_at


def openspec_to_entity(row: OpenSpecChangeRow) -> OpenSpecChange:
    return OpenSpecChange(
        id=row.id,
        repository_id=row.repository_id,
        change_id=row.change_id,
        path=row.path,
        status=OpenSpecStatus(row.status),
        proposal=row.proposal,
        design=row.design,
        tasks=row.tasks,
        affected_specs=list(row.affected_specs or []),
        content_hash=row.content_hash,
    )


def openspec_update_row(row: OpenSpecChangeRow, entity: OpenSpecChange) -> None:
    row.repository_id = entity.repository_id
    row.change_id = entity.change_id
    row.path = entity.path
    row.status = entity.status.value
    row.proposal = entity.proposal
    row.design = entity.design
    row.tasks = entity.tasks
    row.affected_specs = list(entity.affected_specs)
    row.content_hash = entity.content_hash


def issue_to_entity(row: IssueRow) -> Issue:
    return Issue(
        id=row.id,
        repository_id=row.repository_id,
        github_issue_id=row.github_issue_id,
        number=row.number,
        title=row.title,
        body=row.body,
        state=IssueState(row.state),
        author=row.author,
        labels=list(row.labels or []),
        assignees=list(row.assignees or []),
        milestone=row.milestone,
        created_at=row.created_at,
        updated_at=row.updated_at,
        closed_at=row.closed_at,
        comments_count=row.comments_count,
    )


def issue_update_row(row: IssueRow, entity: Issue) -> None:
    row.repository_id = entity.repository_id
    row.github_issue_id = entity.github_issue_id
    row.number = entity.number
    row.title = entity.title
    row.body = entity.body
    row.state = entity.state.value
    row.author = entity.author
    row.labels = list(entity.labels)
    row.assignees = list(entity.assignees)
    row.milestone = entity.milestone
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    row.closed_at = entity.closed_at
    row.comments_count = entity.comments_count


def pr_to_entity(row: PullRequestRow) -> PullRequest:
    return PullRequest(
        id=row.id,
        repository_id=row.repository_id,
        github_pr_id=row.github_pr_id,
        number=row.number,
        title=row.title,
        body=row.body,
        state=PullRequestState(row.state),
        merged=row.merged,
        author=row.author,
        reviewers=list(row.reviewers or []),
        created_at=row.created_at,
        updated_at=row.updated_at,
        closed_at=row.closed_at,
        merged_at=row.merged_at,
        first_review_at=row.first_review_at,
        changed_files=row.changed_files,
        additions=row.additions,
        deletions=row.deletions,
        review_decision=row.review_decision,
    )


def pr_update_row(row: PullRequestRow, entity: PullRequest) -> None:
    row.repository_id = entity.repository_id
    row.github_pr_id = entity.github_pr_id
    row.number = entity.number
    row.title = entity.title
    row.body = entity.body
    row.state = entity.state.value
    row.merged = entity.merged
    row.author = entity.author
    row.reviewers = list(entity.reviewers)
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    row.closed_at = entity.closed_at
    row.merged_at = entity.merged_at
    row.first_review_at = entity.first_review_at
    row.changed_files = entity.changed_files
    row.additions = entity.additions
    row.deletions = entity.deletions
    row.review_decision = entity.review_decision


def source_file_to_entity(row: SourceFileRow) -> SourceFile:
    return SourceFile(
        id=row.id,
        repository_id=row.repository_id,
        path=row.path,
        extension=row.extension,
        language=row.language,
        size_bytes=row.size_bytes,
        sha=row.sha,
        is_binary=row.is_binary,
        is_important=row.is_important,
        important_kind=row.important_kind,
        last_seen_at=row.last_seen_at,
    )


def source_file_update_row(row: SourceFileRow, entity: SourceFile) -> None:
    row.repository_id = entity.repository_id
    row.path = entity.path
    row.extension = entity.extension
    row.language = entity.language
    row.size_bytes = entity.size_bytes
    row.sha = entity.sha
    row.is_binary = entity.is_binary
    row.is_important = entity.is_important
    row.important_kind = entity.important_kind
    row.last_seen_at = entity.last_seen_at


def sync_job_to_entity(row: SyncJobRow) -> SyncJob:
    return SyncJob(
        id=row.id,
        repository_id=row.repository_id,
        mode=IndexingMode(row.mode),
        status=SyncStatus(row.status),
        steps=[
            SyncStepResult(
                step=SyncStep(s["step"]),
                status=SyncStatus(s["status"]),
                error=s.get("error"),
                items_processed=s.get("items_processed", 0),
            )
            for s in (row.steps or [])
        ],
        started_at=row.started_at,
        finished_at=row.finished_at,
        triggered_by=row.triggered_by,
    )


def sync_job_update_row(row: SyncJobRow, entity: SyncJob) -> None:
    row.repository_id = entity.repository_id
    row.mode = entity.mode.value
    row.status = entity.status.value
    row.steps = [
        {
            "step": s.step.value,
            "status": s.status.value,
            "error": s.error,
            "items_processed": s.items_processed,
        }
        for s in entity.steps
    ]
    row.started_at = entity.started_at
    row.finished_at = entity.finished_at
    row.triggered_by = entity.triggered_by


def audit_to_row(entity: AuditRecord) -> AuditLogRow:
    return AuditLogRow(
        id=entity.id,
        subject=entity.subject,
        client_id=entity.client_id,
        operation=entity.operation,
        target=entity.target,
        outcome=entity.outcome,
        occurred_at=entity.occurred_at,
    )


def audit_to_entity(row: AuditLogRow) -> AuditRecord:
    return AuditRecord(
        id=row.id,
        subject=row.subject,
        client_id=row.client_id,
        operation=row.operation,
        target=row.target,
        outcome=row.outcome,
        occurred_at=row.occurred_at,
    )
