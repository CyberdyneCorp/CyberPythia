"""Readiness history recording + regression detection (spec: engineering-intelligence)."""

from datetime import UTC, date, datetime
from uuid import uuid4

from app.application.use_cases.readiness import ReadinessService
from app.domain.entities.readiness_snapshot import ReadinessSnapshot
from app.domain.entities.repository import Repository
from app.domain.services.repository_signals import RepositorySignalsService
from app.domain.value_objects.enums import RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import (
    FakeDocumentPort,
    FakeFilePort,
    FakeOpenSpecPort,
    FakeReadinessHistory,
    FakeRepositoryPort,
)


class _Metrics:
    async def get(self, repository_id):
        return {}


def _repo(full_name: str) -> Repository:
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=hash(full_name) % 100000,
        full_name=RepositoryFullName(full_name), description=None,
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language=None, archived=False, github_updated_at=None, enabled=True,
    )


def _service(repos: FakeRepositoryPort, history: FakeReadinessHistory) -> ReadinessService:
    return ReadinessService(
        repos, FakeFilePort(), FakeDocumentPort(), FakeOpenSpecPort(),
        _Metrics(), RepositorySignalsService(), history=history,
    )


async def test_record_snapshots_writes_one_per_enabled_repo():
    repos, history = FakeRepositoryPort(), FakeReadinessHistory()
    await repos.save(_repo("cyberdyne/a"))
    await repos.save(_repo("cyberdyne/b"))
    n = await _service(repos, history).record_snapshots("cyberdyne")
    assert n == 2
    assert all(len(v) == 1 for v in history.rows.values())  # one day, one row each


async def test_record_snapshots_is_idempotent_per_day():
    repos, history = FakeRepositoryPort(), FakeReadinessHistory()
    await repos.save(_repo("cyberdyne/a"))
    svc = _service(repos, history)
    await svc.record_snapshots()
    await svc.record_snapshots()  # same day again
    assert sum(len(v) for v in history.rows.values()) == 1  # upserted, not duplicated


async def test_organization_regressions_flags_gate_drop():
    repos, history = FakeRepositoryPort(), FakeReadinessHistory()
    dropped, improved = _repo("cyberdyne/dropped"), _repo("cyberdyne/improved")
    await repos.save(dropped)
    await repos.save(improved)
    d1, d2 = date(2026, 7, 8), date(2026, 7, 9)
    ts = datetime(2026, 7, 9, tzinfo=UTC)
    # dropped: READY -> MVP (regression); improved: MVP -> READY (not)
    await history.record(ReadinessSnapshot(dropped.id, d1, ts, "READY"))
    await history.record(ReadinessSnapshot(dropped.id, d2, ts, "MVP"))
    await history.record(ReadinessSnapshot(improved.id, d1, ts, "MVP"))
    await history.record(ReadinessSnapshot(improved.id, d2, ts, "READY"))

    result = await _service(repos, history).organization_regressions("CyberDyne")  # case-insensitive
    assert [r["full_name"] for r in result["regressions"]] == ["cyberdyne/dropped"]
    reg = result["regressions"][0]
    assert reg["from_gate"] == "READY" and reg["to_gate"] == "MVP"
    assert reg["date"] == "2026-07-09"


async def test_repository_history_returns_series():
    repos, history = FakeRepositoryPort(), FakeReadinessHistory()
    r = _repo("cyberdyne/a")
    await repos.save(r)
    await history.record(ReadinessSnapshot(r.id, date(2026, 7, 8), datetime(2026, 7, 8, tzinfo=UTC), "MVP"))
    out = await _service(repos, history).repository_history("cyberdyne/a")
    assert out["history"] == [{"date": "2026-07-08", "gate": "MVP"}]
