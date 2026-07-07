"""Unit tests for incremental single-entity syncs (spec: repository-sync)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.metrics_recompute import MetricsRecomputeService
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.application.use_cases.incremental_sync import IncrementalSyncUseCases
from app.domain.entities.repository import Repository
from app.domain.ports.github_port import GitHubIssueData, GitHubPullRequestData, GitHubRepoData
from app.domain.value_objects.enums import IndexingMode, RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import (
    FakeCipher,
    FakeConnectionPort,
    FakeDocumentPort,
    FakeGitHub,
    FakeIssuePort,
    FakeOpenSpecPort,
    FakePullRequestPort,
    FakeRepositoryPort,
)
from tests.unit.application.test_sync_repository import FakeMetricsStore

NOW = datetime(2026, 7, 7, tzinfo=UTC)


def gh_issue(number, *, is_pr=False, state="open"):
    return GitHubIssueData(
        github_id=number, number=number, title=f"i{number}", body="b", state=state,
        author="alice", labels=["bug"], assignees=[], milestone=None,
        created_at=NOW, updated_at=NOW, closed_at=None, comments_count=1,
        is_pull_request=is_pr,
    )


def gh_pr(number):
    return GitHubPullRequestData(
        github_id=number, number=number, title=f"pr{number}", body="b", state="merged",
        merged=True, author="bob", reviewers=["carol"], created_at=NOW, updated_at=NOW,
        closed_at=NOW, merged_at=NOW, first_review_at=NOW, changed_files=1,
        additions=5, deletions=1, review_decision="APPROVED",
    )


@pytest.fixture
def env():
    github = FakeGitHub()
    connections = FakeConnectionPort()
    connection_uc = GitHubConnectionUseCases(connections, github, FakeCipher())
    repositories = FakeRepositoryPort()
    issues = FakeIssuePort()
    prs = FakePullRequestPort()
    metrics_store = FakeMetricsStore()
    metrics = MetricsRecomputeService(
        issues, prs, FakeDocumentPort(), FakeOpenSpecPort(), metrics_store
    )
    uc = IncrementalSyncUseCases(repositories, issues, prs, github, connection_uc, metrics)
    return {
        "uc": uc, "github": github, "connection_uc": connection_uc,
        "repositories": repositories, "issues": issues, "prs": prs,
        "metrics_store": metrics_store,
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


class TestSyncIssue:
    async def test_upserts_single_issue_and_recomputes_metrics(self, env):
        repo = await seed_repo(env)
        env["github"].issues = [gh_issue(42)]
        assert await env["uc"].sync_issue("cyberdyne/a", 42) is True
        issue = await env["issues"].get_by_number(repo.id, 42)
        assert issue is not None and issue.title == "i42"
        assert repo.id in env["metrics_store"].saved  # metrics recomputed

    async def test_pr_flavored_issue_delegates_to_pr(self, env):
        repo = await seed_repo(env)
        env["github"].issues = [gh_issue(7, is_pr=True)]
        env["github"].pull_requests = [gh_pr(7)]
        await env["uc"].sync_issue("cyberdyne/a", 7)
        assert await env["prs"].get_by_number(repo.id, 7) is not None
        assert await env["issues"].get_by_number(repo.id, 7) is None

    async def test_disabled_repo_no_work(self, env):
        await seed_repo(env, enabled=False)
        env["github"].issues = [gh_issue(42)]
        assert await env["uc"].sync_issue("cyberdyne/a", 42) is False

    async def test_unknown_repo_no_work(self, env):
        assert await env["uc"].sync_issue("cyberdyne/ghost", 1) is False


class TestSyncPullRequest:
    async def test_upserts_single_pr(self, env):
        repo = await seed_repo(env)
        env["github"].pull_requests = [gh_pr(61)]
        assert await env["uc"].sync_pull_request("cyberdyne/a", 61) is True
        pr = await env["prs"].get_by_number(repo.id, 61)
        assert pr.merged and pr.reviewers == ["carol"]
        assert repo.id in env["metrics_store"].saved


class TestRepositoryMetadata:
    async def test_update_metadata(self, env):
        repo = await seed_repo(env)
        env["github"].repos = [
            GitHubRepoData(
                github_id=1, full_name="cyberdyne/a", description="new desc",
                visibility="private", default_branch="develop", primary_language="Go",
                archived=True, updated_at=NOW,
            )
        ]
        assert await env["uc"].update_repository_metadata("cyberdyne/a") is True
        updated = await env["repositories"].get(repo.id)
        assert updated.description == "new desc" and updated.archived

    async def test_remove_repository_disables(self, env):
        repo = await seed_repo(env)
        assert await env["uc"].remove_repository("cyberdyne/a") is True
        assert not (await env["repositories"].get(repo.id)).enabled
