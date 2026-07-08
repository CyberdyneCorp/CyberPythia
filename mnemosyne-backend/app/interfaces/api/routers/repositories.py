"""Repository, content, metrics, search, ask, and context-pack endpoints."""

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.application.audit import AuditService
from app.application.errors import ApplicationError
from app.application.use_cases.code import CodeUseCases
from app.application.use_cases.context import ContextUseCases
from app.application.use_cases.repositories import RepositoryUseCases
from app.domain.value_objects.enums import IndexingMode
from app.interfaces.api.errors import NotFoundError
from app.interfaces.api.mapping import (
    context_pack_response,
    document_response,
    document_summary_response,
    issue_response,
    openspec_response,
    pull_request_response,
    repository_response,
    source_file_response,
    sync_job_response,
    translate_error,
)
from app.interfaces.api.schemas.schemas import (
    MAX_PAGE_SIZE,
    AskRequest,
    AskResponse,
    CodeChunkMatchResponse,
    CodeSearchRequest,
    ContextPackRequest,
    ContextPackResponse,
    FileContentResponse,
    Page,
    RepositoryResponse,
    RepositorySelectionRequest,
    SearchMatchResponse,
    SearchRequest,
    SyncJobResponse,
    paginate,
)
from app.interfaces.api.security import AdminCaller, EntitledCaller, get_audit_service

router = APIRouter(prefix="/api/v1/repos", tags=["repositories"])

PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]


def get_repository_use_cases(request: Request) -> RepositoryUseCases:
    return cast(RepositoryUseCases, request.app.state.container.repository_use_cases)


def get_context_use_cases(request: Request) -> ContextUseCases:
    return cast(ContextUseCases, request.app.state.container.context_use_cases)


def get_code_use_cases(request: Request) -> CodeUseCases:
    return cast(CodeUseCases, request.app.state.container.code_use_cases)


def get_container(request: Request) -> Any:
    return request.app.state.container


RepoUseCases = Annotated[RepositoryUseCases, Depends(get_repository_use_cases)]
CtxUseCases = Annotated[ContextUseCases, Depends(get_context_use_cases)]
CodeUC = Annotated[CodeUseCases, Depends(get_code_use_cases)]
Container = Annotated[object, Depends(get_container)]
Audit = Annotated[AuditService, Depends(get_audit_service)]


@router.get("", response_model=Page[RepositoryResponse])
async def list_repositories(
    caller: EntitledCaller,
    use_cases: RepoUseCases,
    page: PageParam = 1,
    page_size: PageSizeParam = 50,
    enabled_only: bool = False,
    organization: str | None = Query(default=None, max_length=200),
) -> Any:
    repos = await use_cases.list_repositories(
        enabled_only=enabled_only, organization=organization
    )
    return paginate([repository_response(r) for r in repos], page, page_size)


@router.post("/discover/{connection_id}", response_model=list[RepositoryResponse])
async def discover(
    connection_id: UUID, caller: AdminCaller, use_cases: RepoUseCases, audit: Audit
) -> Any:
    try:
        repos = await use_cases.discover(connection_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(caller, "repos.discover", target=str(connection_id))
    return [repository_response(r) for r in repos]


@router.patch("/{repo_id}", response_model=RepositoryResponse)
async def update_selection(
    repo_id: UUID,
    body: RepositorySelectionRequest,
    caller: AdminCaller,
    use_cases: RepoUseCases,
    audit: Audit,
) -> Any:
    try:
        repo = await use_cases.update_selection(
            repo_id,
            enabled=body.enabled,
            mode=IndexingMode(body.indexing_mode) if body.indexing_mode else None,
        )
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(
        caller,
        "repos.selection",
        target=f"{repo.full_name}:enabled={body.enabled},mode={repo.indexing_mode.value}",
    )
    return repository_response(repo)


@router.post("/{repo_id}/sync", response_model=SyncJobResponse, status_code=202)
async def trigger_sync(
    repo_id: UUID, caller: AdminCaller, use_cases: RepoUseCases, audit: Audit
) -> Any:
    try:
        job = await use_cases.trigger_sync(repo_id, triggered_by=caller.subject)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(caller, "repos.sync", target=str(repo_id))
    return sync_job_response(job)


@router.get("/{repo_id}/sync-status", response_model=SyncJobResponse | None)
async def sync_status(repo_id: UUID, caller: EntitledCaller, use_cases: RepoUseCases) -> Any:
    try:
        job = await use_cases.sync_status(repo_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    return sync_job_response(job) if job else None


@router.get("/{repo_id}/summary")
async def summary(
    repo_id: UUID, caller: EntitledCaller, use_cases: RepoUseCases, container: Container
) -> Any:
    try:
        repo = await use_cases.get(repo_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    metrics = await container.metrics_store.get(repo_id)  # type: ignore[attr-defined]
    return {
        "repository": repository_response(repo).model_dump(mode="json"),
        "summary": (metrics or {}).get("summary"),
        "computed_at": (metrics or {}).get("computed_at"),
    }


@router.get("/{repo_id}/docs")
async def list_docs(
    repo_id: UUID,
    caller: EntitledCaller,
    use_cases: RepoUseCases,
    container: Container,
    page: PageParam = 1,
    page_size: PageSizeParam = 50,
) -> Any:
    try:
        await use_cases.get(repo_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    docs = await container.documents.list_by_repository(repo_id)  # type: ignore[attr-defined]
    return paginate([document_summary_response(d) for d in docs], page, page_size)


@router.get("/{repo_id}/docs/{doc_id}")
async def get_doc(repo_id: UUID, doc_id: UUID, caller: EntitledCaller, container: Container) -> Any:
    doc = await container.documents.get(doc_id)  # type: ignore[attr-defined]
    if doc is None or doc.repository_id != repo_id:
        raise NotFoundError(f"document {doc_id} not found")
    return document_response(doc)


@router.get("/{repo_id}/openspec")
async def list_openspec(
    repo_id: UUID, caller: EntitledCaller, use_cases: RepoUseCases, container: Container
) -> Any:
    try:
        await use_cases.get(repo_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    changes = await container.openspec.list_by_repository(repo_id)  # type: ignore[attr-defined]
    return [openspec_response(c) for c in changes]


@router.get("/{repo_id}/issues")
async def list_issues(
    repo_id: UUID,
    caller: EntitledCaller,
    use_cases: RepoUseCases,
    container: Container,
    state: Annotated[str | None, Query(pattern="^(open|closed)$")] = None,
    label: str | None = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 50,
) -> Any:
    try:
        await use_cases.get(repo_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    issues = await container.issues.list_by_repository(  # type: ignore[attr-defined]
        repo_id, state=state, label=label
    )
    return paginate([issue_response(i) for i in issues], page, page_size)


@router.get("/{repo_id}/pull-requests")
async def list_pull_requests(
    repo_id: UUID,
    caller: EntitledCaller,
    use_cases: RepoUseCases,
    container: Container,
    state: Annotated[str | None, Query(pattern="^(open|closed|merged)$")] = None,
    author: str | None = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 50,
) -> Any:
    try:
        await use_cases.get(repo_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    prs = await container.pull_requests.list_by_repository(  # type: ignore[attr-defined]
        repo_id, state=state, author=author
    )
    return paginate([pull_request_response(p) for p in prs], page, page_size)


@router.get("/{repo_id}/files")
async def list_files(
    repo_id: UUID,
    caller: EntitledCaller,
    use_cases: RepoUseCases,
    container: Container,
    page: PageParam = 1,
    page_size: PageSizeParam = 100,
) -> Any:
    try:
        await use_cases.get(repo_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    files = await container.files.list_by_repository(repo_id)  # type: ignore[attr-defined]
    return paginate([source_file_response(f) for f in files], page, page_size)


@router.get("/{repo_id}/metrics")
async def get_metrics(
    repo_id: UUID, caller: EntitledCaller, use_cases: RepoUseCases, container: Container
) -> Any:
    try:
        await use_cases.get(repo_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    metrics = await container.metrics_store.get(repo_id)  # type: ignore[attr-defined]
    if metrics is None:
        raise NotFoundError("metrics not computed yet — run a sync first")
    return metrics


@router.post("/{repo_id}/search", response_model=list[SearchMatchResponse])
async def search_docs(
    repo_id: UUID, body: SearchRequest, caller: EntitledCaller, use_cases: CtxUseCases
) -> Any:
    try:
        matches = await use_cases.search_docs(repo_id, body.query, limit=body.limit)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    return [
        SearchMatchResponse(
            path=m.path, title=m.title, doc_type=m.doc_type, excerpt=m.excerpt, score=m.score
        )
        for m in matches
    ]


@router.post("/{repo_id}/ask", response_model=AskResponse)
async def ask(
    repo_id: UUID, body: AskRequest, caller: EntitledCaller, use_cases: CtxUseCases, audit: Audit
) -> Any:
    try:
        result = await use_cases.ask(repo_id, body.question)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(caller, "repos.ask", target=str(repo_id))
    return result


@router.post("/{repo_id}/context-pack", response_model=ContextPackResponse)
async def build_context_pack(
    repo_id: UUID,
    body: ContextPackRequest,
    caller: EntitledCaller,
    use_cases: CtxUseCases,
    audit: Audit,
) -> Any:
    try:
        pack = await use_cases.build_context_pack(repo_id, body.query)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    await audit.record(caller, "repos.context_pack", target=str(repo_id))
    return context_pack_response(pack)


@router.post("/{repo_id}/code-search", response_model=list[CodeChunkMatchResponse])
async def code_search(
    repo_id: UUID, body: CodeSearchRequest, caller: EntitledCaller, use_cases: CodeUC
) -> Any:
    try:
        matches = await use_cases.search_code(repo_id, body.query, limit=body.limit)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
    return [
        CodeChunkMatchResponse(
            path=m.path, symbol_name=m.symbol_name, chunk_type=m.chunk_type,
            start_line=m.start_line, end_line=m.end_line, excerpt=m.excerpt, score=m.score,
        )
        for m in matches
    ]


@router.get("/{repo_id}/symbols")
async def list_symbols(
    repo_id: UUID,
    caller: EntitledCaller,
    use_cases: CodeUC,
    name: str | None = None,
) -> Any:
    try:
        return await use_cases.symbols(repo_id, name)
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/{repo_id}/files/{file_id}/content", response_model=FileContentResponse)
async def file_content(
    repo_id: UUID, file_id: UUID, caller: EntitledCaller, use_cases: CodeUC
) -> Any:
    try:
        return await use_cases.file_content(repo_id, file_id, caller)
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/{repo_id}/files/{file_id}/related")
async def related_files(
    repo_id: UUID, file_id: UUID, caller: EntitledCaller, use_cases: CodeUC
) -> Any:
    try:
        return await use_cases.related_files(repo_id, file_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc
