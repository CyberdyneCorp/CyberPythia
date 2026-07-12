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


async def test_deliver_digests_sends_only_enabled_nonempty(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "alert_digest_enabled", True)
    sent: list[str] = []

    class _Notifier:
        configured = True

        async def send(self, payload):
            sent.append(payload["organization"])
            return True

    class _Digest:
        async def build(self, org):
            return {"organization": org, "is_empty": org == "quiet"}

    orgs = SimpleNamespace(list_all=lambda: _orgs())

    async def _orgs():
        return [
            SimpleNamespace(login="active", sync_enabled=True),
            SimpleNamespace(login="quiet", sync_enabled=True),      # empty digest → skipped
            SimpleNamespace(login="off", sync_enabled=False),       # disabled → skipped
        ]

    container = SimpleNamespace(notifier=_Notifier(), digest=_Digest(), organizations=orgs)
    await worker._deliver_digests(container)
    assert sent == ["active"]


async def test_deliver_digests_noop_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "alert_digest_enabled", True)
    container = SimpleNamespace(notifier=SimpleNamespace(configured=False))
    await worker._deliver_digests(container)  # must not touch digest/organizations


class _FakePruneStore:
    def __init__(self, removed: int) -> None:
        self.removed = removed
        self.called_with: int | None = None

    async def prune(self, *, retention_days: int) -> int:
        self.called_with = retention_days
        return self.removed


async def test_prune_history_prunes_both_stores_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "history_retention_days", 90)
    metrics, readiness = _FakePruneStore(4), _FakePruneStore(2)
    container = SimpleNamespace(metrics_history=metrics, readiness_history=readiness)
    await worker._prune_history(container)
    assert metrics.called_with == 90
    assert readiness.called_with == 90


async def test_prune_history_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "history_retention_days", 0)
    metrics, readiness = _FakePruneStore(4), _FakePruneStore(2)
    container = SimpleNamespace(metrics_history=metrics, readiness_history=readiness)
    await worker._prune_history(container)
    assert metrics.called_with is None
    assert readiness.called_with is None


async def test_scheduled_full_sync_skips_discovery_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "scheduled_discovery_enabled", False)
    discovery = FakeDiscovery()
    ctx = _ctx(discovery)
    result = await worker.scheduled_full_sync(ctx)
    assert discovery.ran is False
    assert result == "discovered=0 newly_enabled=0 enqueued=3 skipped=1 failed=0"
    assert ctx["container"].sync_runs.recorded[0].discovered == 0
