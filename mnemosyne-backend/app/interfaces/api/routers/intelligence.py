"""Engineering-intelligence endpoints — entitled callers (spec: engineering-intelligence)."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.application.errors import ApplicationError
from app.application.use_cases.cross_repo import CrossRepoService
from app.application.use_cases.delivery_intelligence import DeliveryIntelligenceService
from app.application.use_cases.intelligence import IntelligenceService
from app.application.use_cases.org_intelligence import build_org_intelligence
from app.domain.value_objects.health import RepositoryHealth
from app.interfaces.api.mapping import translate_error
from app.interfaces.api.schemas.schemas import CompareRequest, MemoryCreateRequest
from app.interfaces.api.security import EntitledCaller

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


def get_intelligence(request: Request) -> IntelligenceService:
    return request.app.state.container.intelligence  # type: ignore[no-any-return]


def get_delivery(request: Request) -> DeliveryIntelligenceService:
    return request.app.state.container.delivery_intelligence  # type: ignore[no-any-return]


def get_cross_repo(request: Request) -> CrossRepoService:
    return request.app.state.container.cross_repo  # type: ignore[no-any-return]


Service = Annotated[IntelligenceService, Depends(get_intelligence)]
Delivery = Annotated[DeliveryIntelligenceService, Depends(get_delivery)]
CrossRepo = Annotated[CrossRepoService, Depends(get_cross_repo)]


def _health_dict(health: RepositoryHealth) -> dict[str, Any]:
    return {
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


@router.get("/portfolio")
async def portfolio(
    caller: EntitledCaller, service: Service, organization: str | None = None
) -> Any:
    return asdict(await service.portfolio(organization=organization))


@router.get("/repositories/{repo_id}/health")
async def health(repo_id: UUID, caller: EntitledCaller, service: Service) -> Any:
    try:
        return _health_dict(await service.health(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/delivery")
async def delivery(repo_id: UUID, caller: EntitledCaller, service: Service) -> Any:
    try:
        return asdict(await service.delivery(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/backlog")
async def backlog(repo_id: UUID, caller: EntitledCaller, service: Service) -> Any:
    try:
        return asdict(await service.backlog(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/review-bottlenecks")
async def review_bottlenecks(repo_id: UUID, caller: EntitledCaller, service: Service) -> Any:
    try:
        return asdict(await service.review_bottlenecks(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/maintenance-risk")
async def maintenance_risk(repo_id: UUID, caller: EntitledCaller, service: Service) -> Any:
    try:
        return asdict(await service.maintenance_risk(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/onboarding")
async def onboarding(repo_id: UUID, caller: EntitledCaller, service: Service) -> Any:
    try:
        return await service.onboarding_summary(repo_id)
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.post("/compare")
async def compare(body: CompareRequest, caller: EntitledCaller, service: Service) -> Any:
    try:
        return {"comparison": await service.compare(body.repository_ids)}
    except ApplicationError as exc:
        raise translate_error(exc) from exc


# -- PM/PO delivery endpoints ---------------------------------------------------


@router.get("/repositories/{repo_id}/flow")
async def flow(repo_id: UUID, caller: EntitledCaller, delivery: Delivery) -> Any:
    try:
        return asdict(await delivery.flow(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/throughput")
async def throughput(repo_id: UUID, caller: EntitledCaller, delivery: Delivery) -> Any:
    try:
        return asdict(await delivery.throughput(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/forecast")
async def forecast(repo_id: UUID, caller: EntitledCaller, delivery: Delivery) -> Any:
    try:
        return asdict(await delivery.forecast(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/work-mix")
async def work_mix(repo_id: UUID, caller: EntitledCaller, delivery: Delivery) -> Any:
    try:
        return asdict(await delivery.work_mix(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/quality")
async def quality(repo_id: UUID, caller: EntitledCaller, delivery: Delivery) -> Any:
    try:
        return asdict(await delivery.quality(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/milestones")
async def milestones(repo_id: UUID, caller: EntitledCaller, delivery: Delivery) -> Any:
    try:
        return {"milestones": [asdict(m) for m in await delivery.milestones(repo_id)]}
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/repositories/{repo_id}/team-load")
async def team_load(repo_id: UUID, caller: EntitledCaller, delivery: Delivery) -> Any:
    try:
        return asdict(await delivery.team_load(repo_id))
    except ApplicationError as exc:
        raise translate_error(exc) from exc


@router.get("/delivery-scorecard")
async def delivery_scorecard(
    caller: EntitledCaller, delivery: Delivery, organization: str | None = None
) -> Any:
    board = await delivery.delivery_scorecard(organization=organization)
    return {"scorecard": [asdict(e) for e in board]}


@router.get("/organizations/{organization}/intelligence")
async def organization_intelligence(
    organization: str, caller: EntitledCaller, service: Service, delivery: Delivery
) -> Any:
    portfolio = await service.portfolio(organization=organization)
    scorecard = await delivery.delivery_scorecard(organization=organization)
    return build_org_intelligence(organization, portfolio, scorecard)


# -- cross-repo endpoints (mirror the MCP cross-repo tools) -------------------


@router.get("/search")
async def search(
    caller: EntitledCaller,
    cross_repo: CrossRepo,
    query: str,
    kind: Annotated[str, Query(pattern="^(docs|code|issues)$")] = "docs",
    organization: str | None = None,
    limit: int = 8,
) -> Any:
    results = await cross_repo.search(
        query, kind=kind, organization=organization, limit=limit
    )
    return {"results": results}


@router.get("/stale-issues")
async def stale_issues(
    caller: EntitledCaller, cross_repo: CrossRepo,
    organization: str | None = None, threshold_days: int = 30, limit: int = 50,
) -> Any:
    return {"stale": await cross_repo.find_stale_issues(
        organization=organization, threshold_days=threshold_days, limit=limit
    )}


@router.get("/stale-prs")
async def stale_prs(
    caller: EntitledCaller, cross_repo: CrossRepo,
    organization: str | None = None, threshold_days: int = 30, limit: int = 50,
) -> Any:
    return {"stale": await cross_repo.find_stale_prs(
        organization=organization, threshold_days=threshold_days, limit=limit
    )}


@router.get("/recent-activity")
async def recent_activity(
    caller: EntitledCaller, cross_repo: CrossRepo,
    organization: str | None = None, limit: int = 15,
) -> Any:
    return await cross_repo.recent_activity(organization=organization, limit=limit)


@router.get("/organizations/{organization}/capabilities")
async def organization_capabilities(
    organization: str, caller: EntitledCaller, request: Request
) -> Any:
    """What the org can do right now: union of capabilities + per-project briefs."""
    service = request.app.state.container.capabilities
    return await service.organization_capabilities(organization)


@router.get("/organizations/{organization}/openspec-coverage")
async def organization_openspec_coverage(
    organization: str, caller: EntitledCaller, request: Request
) -> Any:
    """Repositories in the org partitioned into with / without OpenSpec + coverage ratio."""
    service = request.app.state.container.capabilities
    return await service.organization_openspec_coverage(organization)


@router.get("/organizations/{organization}/readiness")
async def organization_readiness(
    organization: str, caller: EntitledCaller, request: Request
) -> Any:
    """MVP/READY/DONE distribution for the org + each repo's gate and gaps."""
    return await request.app.state.container.readiness.organization_readiness(organization)


@router.get("/organizations/{organization}/readiness-regressions")
async def organization_readiness_regressions(
    organization: str, caller: EntitledCaller, request: Request
) -> Any:
    """Repositories whose latest readiness gate dropped below the previous one."""
    return await request.app.state.container.readiness.organization_regressions(organization)


@router.get("/organizations/{organization}/digest")
async def organization_digest(
    organization: str, caller: EntitledCaller, request: Request
) -> Any:
    """Attention digest: readiness regressions + stale issues/PRs + at-risk milestones."""
    return await request.app.state.container.digest.build(organization)


@router.get("/organizations/{organization}/vulnerabilities")
async def organization_vulnerabilities(
    organization: str, caller: EntitledCaller, request: Request
) -> Any:
    """Repositories with open critical/high Dependabot alerts, most-critical first."""
    return await request.app.state.container.security.organization_vulnerabilities(organization)


@router.post("/organizations/{organization}/memories", status_code=201)
async def create_organization_memory(
    organization: str, body: MemoryCreateRequest, caller: EntitledCaller, request: Request
) -> Any:
    """Record a durable memory scoped to the organization."""
    return await request.app.state.container.memory.remember_organization(
        organization, content=body.content, kind=body.kind, author=caller.subject)


@router.get("/organizations/{organization}/memories")
async def list_organization_memories(
    organization: str, caller: EntitledCaller, request: Request,
    query: str | None = None, kind: str | None = None, limit: int = 50,
) -> Any:
    """List the organization's memories, newest first."""
    return await request.app.state.container.memory.recall_organization(
        organization, query=query, kind=kind, limit=limit)
