from uuid import uuid4

from app.application.errors import SyncAlreadyRunningError, UnknownResourceError
from app.application.use_cases.scheduled_sync import ScheduledSyncService
from app.domain.entities.repository import Repository
from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import FakeRepositoryPort


def make_repo(name, *, enabled=True) -> Repository:
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=hash(name) % 100000,
        full_name=RepositoryFullName(name), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=False, github_updated_at=None,
        enabled=enabled, indexing_mode=IndexingMode.PROJECT_INTELLIGENCE,
    )


class RecordingTrigger:
    def __init__(self, *, raise_for=None) -> None:
        self.calls: list = []
        self._raise_for = raise_for or {}

    async def trigger_sync(self, repository_id, *, triggered_by, defer_seconds=0.0):
        self.calls.append((repository_id, triggered_by, defer_seconds))
        exc = self._raise_for.get(repository_id)
        if exc is not None:
            raise exc
        return object()


async def _seed(repos, *specs):
    made = []
    for name, enabled in specs:
        r = make_repo(name, enabled=enabled)
        await repos.save(r)
        made.append(r)
    return made


async def test_enqueues_all_enabled_repos_only() -> None:
    repos = FakeRepositoryPort()
    a, b, c = await _seed(
        repos, ("cyberdyne/a", True), ("cyberdyne/b", True), ("cyberdyne/c", False)
    )
    trigger = RecordingTrigger()
    summary = await ScheduledSyncService(repos, trigger).run()
    assert summary.enqueued == 2
    enqueued_ids = {rid for rid, _, _ in trigger.calls}
    assert enqueued_ids == {a.id, b.id}
    assert c.id not in enqueued_ids
    assert all(by == "scheduler" for _, by, _ in trigger.calls)


async def test_staggers_enqueues_with_increasing_defer() -> None:
    repos = FakeRepositoryPort()
    await _seed(
        repos, ("cyberdyne/a", True), ("cyberdyne/b", True), ("cyberdyne/c", True)
    )
    trigger = RecordingTrigger()
    await ScheduledSyncService(repos, trigger, stagger_seconds=5.0).run()
    defers = sorted(defer for _, _, defer in trigger.calls)
    assert defers == [0.0, 5.0, 10.0]  # 0, 1x, 2x stagger


async def test_no_defer_when_stagger_zero() -> None:
    repos = FakeRepositoryPort()
    await _seed(repos, ("cyberdyne/a", True), ("cyberdyne/b", True))
    trigger = RecordingTrigger()
    await ScheduledSyncService(repos, trigger).run()  # default stagger 0
    assert all(defer == 0.0 for _, _, defer in trigger.calls)


async def test_skips_repos_in_disabled_organizations() -> None:
    from tests.unit.application.fakes import FakeOrganizationPort

    repos = FakeRepositoryPort()
    # aminitech disabled, cyberdyne enabled, unknown-org repo fail-open
    a, b, c = await _seed(
        repos, ("aminitech/x", True), ("cyberdyne/y", True), ("epicgames/z", True)
    )
    orgs = FakeOrganizationPort()
    await orgs.upsert_many(["aminitech", "cyberdyne"], default_enabled=True)
    await orgs.set_enabled("aminitech", enabled=False)
    trigger = RecordingTrigger()
    summary = await ScheduledSyncService(repos, trigger, organizations=orgs).run()
    enqueued_ids = {rid for rid, _, _ in trigger.calls}
    assert a.id not in enqueued_ids  # aminitech disabled -> skipped
    assert b.id in enqueued_ids  # cyberdyne enabled
    assert c.id in enqueued_ids  # epicgames unknown -> fail-open
    assert summary.enqueued == 2 and summary.skipped == 1


async def test_skips_already_running() -> None:
    repos = FakeRepositoryPort()
    a, _b = await _seed(repos, ("cyberdyne/a", True), ("cyberdyne/b", True))
    trigger = RecordingTrigger(raise_for={a.id: SyncAlreadyRunningError("cyberdyne/a")})
    summary = await ScheduledSyncService(repos, trigger).run()
    assert summary.enqueued == 1 and summary.skipped == 1 and summary.failed == 0


async def test_one_failure_does_not_stop_others() -> None:
    repos = FakeRepositoryPort()
    _a, b, _c = await _seed(
        repos, ("cyberdyne/a", True), ("cyberdyne/b", True), ("cyberdyne/c", True)
    )
    trigger = RecordingTrigger(raise_for={b.id: RuntimeError("boom")})
    summary = await ScheduledSyncService(repos, trigger).run()
    assert summary.enqueued == 2 and summary.failed == 1
    assert len(trigger.calls) == 3  # all attempted


async def test_application_error_is_skipped_not_failed() -> None:
    repos = FakeRepositoryPort()
    (a,) = await _seed(repos, ("cyberdyne/a", True))
    trigger = RecordingTrigger(raise_for={a.id: UnknownResourceError("not enabled")})
    summary = await ScheduledSyncService(repos, trigger).run()
    assert summary.skipped == 1 and summary.failed == 0


async def test_empty_when_no_enabled_repos() -> None:
    repos = FakeRepositoryPort()
    await _seed(repos, ("cyberdyne/c", False))
    summary = await ScheduledSyncService(repos, RecordingTrigger()).run()
    assert summary == type(summary)(enqueued=0, skipped=0, failed=0)


async def test_orders_least_recently_synced_first() -> None:
    from datetime import UTC, datetime

    repos = FakeRepositoryPort()
    recent = make_repo("cyberdyne/recent")
    recent.last_synced_at = datetime(2026, 7, 12, tzinfo=UTC)
    old = make_repo("cyberdyne/old")
    old.last_synced_at = datetime(2026, 7, 1, tzinfo=UTC)
    never = make_repo("cyberdyne/never")  # last_synced_at is None
    for r in (recent, old, never):
        await repos.save(r)
    trigger = RecordingTrigger()
    await ScheduledSyncService(repos, trigger).run()
    order = [rid for rid, _, _ in trigger.calls]
    assert order == [never.id, old.id, recent.id]  # never -> oldest -> newest


async def test_per_run_cap_defers_remainder() -> None:
    from datetime import UTC, datetime

    repos = FakeRepositoryPort()
    made = []
    for i in range(4):
        r = make_repo(f"cyberdyne/r{i}")
        r.last_synced_at = datetime(2026, 7, 1 + i, tzinfo=UTC)  # r0 oldest
        await repos.save(r)
        made.append(r)
    trigger = RecordingTrigger()
    summary = await ScheduledSyncService(repos, trigger, max_repos_per_run=2).run()
    assert summary.enqueued == 2
    # only the two least-recently-synced (r0, r1) are attempted this run
    assert [rid for rid, _, _ in trigger.calls] == [made[0].id, made[1].id]


async def test_fairness_a_failed_repo_is_prioritised_next_run() -> None:
    from datetime import UTC, datetime

    repos = FakeRepositoryPort()
    synced = make_repo("cyberdyne/synced")
    synced.last_synced_at = datetime(2026, 7, 12, tzinfo=UTC)  # succeeded before
    stale = make_repo("cyberdyne/stale")
    stale.last_synced_at = datetime(2026, 7, 1, tzinfo=UTC)  # failed before -> stale
    for r in (synced, stale):
        await repos.save(r)
    trigger = RecordingTrigger()
    await ScheduledSyncService(repos, trigger, max_repos_per_run=1).run()
    # under a tight cap, the previously-failed (stale) repo is attempted first
    assert [rid for rid, _, _ in trigger.calls] == [stale.id]
