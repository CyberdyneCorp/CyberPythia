"""Unit tests for webhook delivery processing (spec: webhooks)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.metrics_recompute import MetricsRecomputeService
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.application.use_cases.incremental_sync import IncrementalSyncUseCases
from app.application.use_cases.process_webhook import ProcessWebhookDelivery
from app.application.use_cases.repositories import RepositoryUseCases
from app.domain.entities.repository import Repository
from app.domain.entities.webhook_event import WebhookEvent
from app.domain.ports.github_port import GitHubIssueData, GitHubPullRequestData
from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import (
    FakeCipher,
    FakeConnectionPort,
    FakeDocumentPort,
    FakeGitHub,
    FakeGitHubAppAuth,
    FakeIssuePort,
    FakeOpenSpecPort,
    FakePullRequestPort,
    FakeQueue,
    FakeRepositoryPort,
    FakeSyncJobPort,
    FakeSyncLock,
)
from tests.unit.application.test_sync_repository import FakeMetricsStore

NOW = datetime(2026, 7, 7, tzinfo=UTC)


class FakeDeliveryPort:
    def __init__(self):
        self.seen: dict[str, str] = {}

    async def exists(self, delivery_id):
        return delivery_id in self.seen

    async def record(self, delivery):
        self.seen[delivery.delivery_id] = delivery.outcome

    async def list_recent(self, limit=100):
        return []


def event(evt, action=None, payload=None, delivery_id="d1", full_name="cyberdyne/a"):
    return WebhookEvent(
        delivery_id=delivery_id, event=evt, action=action,
        installation_id="99", repository_full_name=full_name, payload=payload or {},
    )


@pytest.fixture
def env():
    github = FakeGitHub()
    connections = FakeConnectionPort()
    connection_uc = GitHubConnectionUseCases(
        connections, github, FakeCipher(), app_auth=FakeGitHubAppAuth()
    )
    repositories = FakeRepositoryPort()
    issues = FakeIssuePort()
    prs = FakePullRequestPort()
    queue = FakeQueue()
    sync_jobs = FakeSyncJobPort()
    lock = FakeSyncLock()
    repo_uc = RepositoryUseCases(
        repositories, connections, connection_uc, github, sync_jobs, queue, lock
    )
    metrics = MetricsRecomputeService(
        issues, prs, FakeDocumentPort(), FakeOpenSpecPort(), FakeMetricsStore()
    )
    incremental = IncrementalSyncUseCases(
        repositories, issues, prs, github, connection_uc, metrics
    )
    deliveries = FakeDeliveryPort()
    processor = ProcessWebhookDelivery(deliveries, connections, incremental, repo_uc)
    return {
        "processor": processor, "github": github, "connection_uc": connection_uc,
        "repositories": repositories, "issues": issues, "prs": prs,
        "queue": queue, "deliveries": deliveries, "connections": connections,
    }


async def seed_repo(env, enabled=True):
    connection = await env["connection_uc"].connect("ghp_secret_ab12")
    repo = Repository(
        id=uuid4(), connection_id=connection.id, github_id=1,
        full_name=RepositoryFullName("cyberdyne/a"), description="d",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=False, github_updated_at=NOW,
        enabled=enabled, indexing_mode=IndexingMode.PROJECT_INTELLIGENCE, last_synced_at=NOW,
    )
    await env["repositories"].save(repo)
    return repo


def gh_issue(n):
    return GitHubIssueData(
        github_id=n, number=n, title=f"i{n}", body=None, state="open", author="a",
        labels=[], assignees=[], milestone=None, created_at=NOW, updated_at=NOW,
        closed_at=None, comments_count=0, is_pull_request=False,
    )


def gh_pr(n):
    return GitHubPullRequestData(
        github_id=n, number=n, title=f"pr{n}", body=None, state="open", merged=False,
        author="b", reviewers=[], created_at=NOW, updated_at=NOW, closed_at=None,
        merged_at=None, first_review_at=None, changed_files=1, additions=1, deletions=0,
        review_decision=None,
    )


class TestDispatch:
    async def test_push_enqueues_sync(self, env):
        await seed_repo(env)
        outcome = await env["processor"].process(event("push"))
        assert outcome == "processed"
        assert env["queue"].jobs  # a sync was enqueued

    async def test_issue_event_upserts(self, env):
        repo = await seed_repo(env)
        env["github"].issues = [gh_issue(42)]
        outcome = await env["processor"].process(
            event("issues", "opened", {"issue": {"number": 42}})
        )
        assert outcome == "processed"
        assert await env["issues"].get_by_number(repo.id, 42) is not None

    async def test_pull_request_event_upserts(self, env):
        repo = await seed_repo(env)
        env["github"].pull_requests = [gh_pr(61)]
        outcome = await env["processor"].process(
            event("pull_request", "opened", {"pull_request": {"number": 61}})
        )
        assert outcome == "processed"
        assert await env["prs"].get_by_number(repo.id, 61) is not None

    async def test_repository_deleted_disables(self, env):
        repo = await seed_repo(env)
        outcome = await env["processor"].process(event("repository", "deleted"))
        assert outcome == "processed"
        assert not (await env["repositories"].get(repo.id)).enabled

    async def test_event_for_non_indexed_repo_ignored(self, env):
        await seed_repo(env, enabled=False)
        env["github"].issues = [gh_issue(42)]
        outcome = await env["processor"].process(
            event("issues", "opened", {"issue": {"number": 42}})
        )
        assert outcome == "ignored"

    async def test_unknown_event_ignored(self, env):
        await seed_repo(env)
        assert await env["processor"].process(event("star", "created")) == "ignored"


class TestIdempotency:
    async def test_duplicate_delivery_not_reprocessed(self, env):
        await seed_repo(env)
        first = await env["processor"].process(event("push", delivery_id="dup"))
        assert first == "processed"
        env["queue"].jobs.clear()
        second = await env["processor"].process(event("push", delivery_id="dup"))
        assert second == "duplicate"
        assert env["queue"].jobs == []  # no new work

    async def test_delivery_recorded_with_outcome(self, env):
        await seed_repo(env)
        await env["processor"].process(event("push", delivery_id="d-rec"))
        assert env["deliveries"].seen["d-rec"] == "processed"


class TestReconcile:
    async def test_installation_event_rediscovers(self, env):
        from app.domain.ports.github_port import GitHubRepoData

        # register an app connection whose installation matches the event
        env["github"].repos = [
            GitHubRepoData(
                github_id=5, full_name="cyberdyne/new", description="d",
                visibility="private", default_branch="main", primary_language="Go",
                archived=False, updated_at=NOW,
            )
        ]
        from app.domain.entities.github_connection import GitHubConnection
        from app.domain.value_objects.enums import ConnectionKind

        conn = GitHubConnection(
            id=uuid4(), owner="cyberdyne", owner_type="Organization",
            kind=ConnectionKind.GITHUB_APP, app_id="1", installation_id="99",
            encrypted_private_key=b"pk", encrypted_webhook_secret=b"wh",
        )
        await env["connections"].save(conn)
        outcome = await env["processor"].process(
            event("installation_repositories", "added")
        )
        assert outcome == "processed"
        assert await env["repositories"].get_by_full_name("cyberdyne/new") is not None
