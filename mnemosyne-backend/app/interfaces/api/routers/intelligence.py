"""Engineering-intelligence endpoints — entitled callers (spec: engineering-intelligence)."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.application.errors import ApplicationError
from app.application.use_cases.delivery_intelligence import DeliveryIntelligenceService
from app.application.use_cases.intelligence import IntelligenceService
from app.domain.value_objects.health import RepositoryHealth
from app.interfaces.api.mapping import translate_error
from app.interfaces.api.schemas.schemas import CompareRequest
from app.interfaces.api.security import EntitledCaller

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


def get_intelligence(request: Request) -> IntelligenceService:
    return request.app.state.container.intelligence  # type: ignore[no-any-return]


def get_delivery(request: Request) -> DeliveryIntelligenceService:
    return request.app.state.container.delivery_intelligence  # type: ignore[no-any-return]


Service = Annotated[IntelligenceService, Depends(get_intelligence)]
Delivery = Annotated[DeliveryIntelligenceService, Depends(get_delivery)]


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
async def portfolio(caller: EntitledCaller, service: Service) -> Any:
    return asdict(await service.portfolio())


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
async def delivery_scorecard(caller: EntitledCaller, delivery: Delivery) -> Any:
    return {"scorecard": [asdict(e) for e in await delivery.delivery_scorecard()]}
