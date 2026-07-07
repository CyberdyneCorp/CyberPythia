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


async def test_scheduled_full_sync_invokes_service() -> None:
    calls = []

    class FakeScheduled:
        async def run(self):
            calls.append(True)
            return ScheduledSyncSummary(enqueued=3, skipped=1, failed=0)

    ctx = {"container": SimpleNamespace(scheduled_sync=FakeScheduled())}
    result = await worker.scheduled_full_sync(ctx)
    assert calls == [True]
    assert result == "enqueued=3 skipped=1 failed=0"
