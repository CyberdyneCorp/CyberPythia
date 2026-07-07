"""Request/response schemas (spec: rest-api)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

MAX_PAGE_SIZE = 100


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    next_page: int | None


def paginate(items: list[Any], page: int, page_size: int) -> Page[Any]:
    start = (page - 1) * page_size
    window = items[start : start + page_size]
    has_more = start + page_size < len(items)
    return Page(
        items=window, page=page, page_size=page_size, next_page=page + 1 if has_more else None
    )


# -- github connections -------------------------------------------------------


class ConnectRequest(BaseModel):
    token: str = Field(min_length=8, description="Fine-grained GitHub PAT (read-only)")


class ConnectionResponse(BaseModel):
    id: UUID
    owner: str
    owner_type: str
    kind: str
    token_hint: str
    permissions: list[str]
    status: str
    installation_id: str | None = None


class AppConnectRequest(BaseModel):
    app_id: str = Field(min_length=1)
    installation_id: str = Field(min_length=1)
    private_key: str = Field(min_length=40, description="App private key PEM")
    webhook_secret: str = Field(min_length=1)


class WebhookDeliveryResponse(BaseModel):
    delivery_id: str
    event: str
    action: str | None
    repository_full_name: str | None
    outcome: str
    received_at: datetime


class ConnectionTestResponse(BaseModel):
    ok: bool
    status: str
    permissions: list[str] | None = None
    rate_limit: dict[str, int] | None = None


# -- repositories --------------------------------------------------------------


class RepositoryResponse(BaseModel):
    id: UUID
    full_name: str
    description: str | None
    visibility: str
    default_branch: str
    primary_language: str | None
    archived: bool
    enabled: bool
    indexing_mode: str
    last_synced_at: datetime | None


class RepositorySelectionRequest(BaseModel):
    enabled: bool
    indexing_mode: str | None = Field(
        default=None,
        pattern="^(docs_only|project_intelligence|code_metadata|code_context|full_context)$",
    )


class SyncStepResponse(BaseModel):
    step: str
    status: str
    error: str | None
    items_processed: int


class SyncJobResponse(BaseModel):
    id: UUID
    repository_id: UUID
    mode: str
    status: str
    steps: list[SyncStepResponse]
    started_at: datetime | None
    finished_at: datetime | None


# -- content -------------------------------------------------------------------


class DocumentSummaryResponse(BaseModel):
    id: UUID
    path: str
    type: str
    title: str
    quarantined: bool
    captured_at: datetime | None


class DocumentResponse(DocumentSummaryResponse):
    content: str | None


class OpenSpecChangeResponse(BaseModel):
    change_id: str
    path: str
    status: str
    proposal: str | None
    design: str | None
    tasks: str | None
    affected_specs: list[str]


class IssueResponse(BaseModel):
    number: int
    title: str
    state: str
    author: str | None
    labels: list[str]
    assignees: list[str]
    created_at: datetime | None
    closed_at: datetime | None
    resolution_time_seconds: float | None
    comments_count: int


class PullRequestResponse(BaseModel):
    number: int
    title: str
    state: str
    merged: bool
    author: str | None
    reviewers: list[str]
    created_at: datetime | None
    merged_at: datetime | None
    time_to_merge_seconds: float | None
    time_to_first_review_seconds: float | None
    additions: int
    deletions: int


class SourceFileResponse(BaseModel):
    path: str
    extension: str | None
    language: str | None
    size_bytes: int
    is_binary: bool
    is_important: bool
    important_kind: str | None


# -- search / ask / context packs ----------------------------------------------


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=8, ge=1, le=25)


class SearchMatchResponse(BaseModel):
    path: str
    title: str
    doc_type: str
    excerpt: str
    score: float


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    grounded: bool


class CodeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=8, ge=1, le=25)


class CodeChunkMatchResponse(BaseModel):
    path: str
    symbol_name: str | None
    chunk_type: str
    start_line: int
    end_line: int
    excerpt: str
    score: float


class FileContentResponse(BaseModel):
    path: str
    language: str | None
    size_bytes: int
    content: str


class ContextPackRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)


class ContextPackResponse(BaseModel):
    id: UUID
    repository_id: UUID
    query: str
    mode: str
    repository_summary: str
    relevant_docs: list[dict[str, Any]]
    relevant_openspec_changes: list[dict[str, Any]]
    relevant_issues: list[dict[str, Any]]
    relevant_pull_requests: list[dict[str, Any]]
    relevant_files: list[dict[str, Any]]
    source_chunks: list[dict[str, Any]]
    risks: list[str]
    suggested_next_steps: list[str]
    excluded_categories: list[str]
    sync_timestamp: datetime | None
    created_at: datetime | None
