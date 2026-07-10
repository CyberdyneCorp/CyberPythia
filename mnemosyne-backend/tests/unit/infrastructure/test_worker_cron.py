"""Worker cron wiring for the scheduled daily sync."""

from types import SimpleNamespace

import app.infrastructure.queue.worker as worker
from app.application.use_cases.scheduled_sync import ScheduledSyncSummary


def test_cron_registered_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "scheduled_sync_enabled", True)
    monkeypatch.setattr(worker._settings, "scheduled_sync_hour", 5)
    monkeypatch.setattr(worker._settings, "scheduled_sync_minute", 30)
    jobs = worker._cron_jobs()
    assert len(jobs) == 1


def test_no_cron_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "scheduled_sync_enabled", False)
    assert worker._cron_jobs() == []


class FakeSync:
    async def run(self):
        return ScheduledSyncSummary(enqueued=3, skipped=1, failed=0)


class FakeDiscovery:
    def __init__(self):
        self.ran = False

    async def run(self):
        self.ran = True
        return SimpleNamespace(discovered=345, newly_enabled=2, skipped_archived=1)


class FakeRuns:
    def __init__(self):
        self.recorded = []

    async def record(self, run):
        self.recorded.append(run)


def _ctx(discovery):
    return {
        "container": SimpleNamespace(
            scheduled_sync=FakeSync(), scheduled_discovery=discovery, sync_runs=FakeRuns()
        )
    }


async def test_scheduled_full_sync_chains_discovery_then_sync(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "scheduled_discovery_enabled", True)
    discovery = FakeDiscovery()
    ctx = _ctx(discovery)
    result = await worker.scheduled_full_sync(ctx)
    assert discovery.ran is True
    assert "discovered=345 newly_enabled=2 " in result
    assert "enqueued=3 skipped=1 failed=0" in result
    # records a SyncRun with the combined counters
    runs = ctx["container"].sync_runs.recorded
    assert len(runs) == 1
    assert runs[0].discovered == 345 and runs[0].newly_enabled == 2
    assert runs[0].enqueued == 3 and runs[0].failed == 0


async def test_delete_connection_job_delegates_to_use_case() -> None:
    from uuid import uuid4

    called = {}

    class FakeConnUC:
        async def perform_delete(self, connection_id):
            called["id"] = connection_id

    cid = uuid4()
    ctx = {"container": SimpleNamespace(connection_use_cases=FakeConnUC())}
    result = await worker.delete_connection(ctx, str(cid))
    assert called["id"] == cid
    assert result == str(cid)


def test_delete_connection_registered() -> None:
    assert worker.delete_connection in worker.WorkerSettings.functions


async def test_scheduled_full_sync_skips_discovery_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "scheduled_discovery_enabled", False)
    discovery = FakeDiscovery()
    ctx = _ctx(discovery)
    result = await worker.scheduled_full_sync(ctx)
    assert discovery.ran is False
    assert result == "discovered=0 newly_enabled=0 enqueued=3 skipped=1 failed=0"
    assert ctx["container"].sync_runs.recorded[0].discovered == 0
