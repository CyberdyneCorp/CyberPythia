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


async def test_scheduled_full_sync_chains_discovery_then_sync(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "scheduled_discovery_enabled", True)
    discovery = FakeDiscovery()
    ctx = {
        "container": SimpleNamespace(scheduled_sync=FakeSync(), scheduled_discovery=discovery)
    }
    result = await worker.scheduled_full_sync(ctx)
    assert discovery.ran is True
    assert "discovered=345 newly_enabled=2 " in result
    assert "enqueued=3 skipped=1 failed=0" in result


async def test_scheduled_full_sync_skips_discovery_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(worker._settings, "scheduled_discovery_enabled", False)
    discovery = FakeDiscovery()
    ctx = {
        "container": SimpleNamespace(scheduled_sync=FakeSync(), scheduled_discovery=discovery)
    }
    result = await worker.scheduled_full_sync(ctx)
    assert discovery.ran is False
    assert result == "enqueued=3 skipped=1 failed=0"
