from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.github_connection import GitHubConnection
from app.domain.entities.issue import Issue
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.entities.sync_job import SyncJob, SyncStatus, SyncStep
from app.domain.value_objects.enums import (
    IndexingMode,
    IssueState,
    PullRequestState,
    RepositoryVisibility,
)
from app.domain.value_objects.full_name import RepositoryFullName

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


def make_repo(**kw) -> Repository:
    defaults = dict(
        id=uuid4(),
        connection_id=uuid4(),
        github_id=1,
        full_name=RepositoryFullName("cyberdyne/matforge"),
        description=None,
        visibility=RepositoryVisibility.PRIVATE,
        default_branch="main",
        primary_language="Python",
        archived=False,
        github_updated_at=None,
    )
    defaults.update(kw)
    return Repository(**defaults)


def make_issue(**kw) -> Issue:
    defaults = dict(
        id=uuid4(),
        repository_id=uuid4(),
        github_issue_id=10,
        number=1,
        title="t",
        body=None,
        state=IssueState.OPEN,
        author="alice",
    )
    defaults.update(kw)
    return Issue(**defaults)


def make_pr(**kw) -> PullRequest:
    defaults = dict(
        id=uuid4(),
        repository_id=uuid4(),
        github_pr_id=20,
        number=2,
        title="t",
        body=None,
        state=PullRequestState.OPEN,
        merged=False,
        author="bob",
    )
    defaults.update(kw)
    return PullRequest(**defaults)


class TestRepository:
    def test_enable_sets_mode(self):
        repo = make_repo()
        repo.enable(IndexingMode.PROJECT_INTELLIGENCE)
        assert repo.enabled and repo.indexing_mode is IndexingMode.PROJECT_INTELLIGENCE

    def test_disable(self):
        repo = make_repo(enabled=True)
        repo.disable()
        assert not repo.enabled

    def test_synced_property(self):
        assert not make_repo().synced
        assert make_repo(last_synced_at=NOW).synced


class TestIssue:
    def test_resolution_time_for_closed_issue(self):
        issue = make_issue(
            state=IssueState.CLOSED, created_at=NOW - timedelta(days=2), closed_at=NOW
        )
        assert issue.resolution_time_seconds == timedelta(days=2).total_seconds()

    def test_resolution_time_none_for_open_issue(self):
        assert make_issue(created_at=NOW).resolution_time_seconds is None

    def test_stale_open_issue(self):
        issue = make_issue(created_at=NOW - timedelta(days=90), updated_at=NOW - timedelta(days=40))
        assert issue.is_stale(NOW, threshold_days=30)

    def test_recently_updated_issue_not_stale(self):
        issue = make_issue(created_at=NOW - timedelta(days=90), updated_at=NOW - timedelta(days=2))
        assert not issue.is_stale(NOW, threshold_days=30)

    def test_closed_issue_never_stale(self):
        issue = make_issue(
            state=IssueState.CLOSED, created_at=NOW - timedelta(days=90), closed_at=NOW
        )
        assert not issue.is_stale(NOW, threshold_days=30)


class TestPullRequest:
    def test_time_to_merge(self):
        pr = make_pr(
            state=PullRequestState.MERGED,
            merged=True,
            created_at=NOW - timedelta(hours=10),
            merged_at=NOW,
        )
        assert pr.time_to_merge_seconds == timedelta(hours=10).total_seconds()

    def test_time_to_merge_none_when_not_merged(self):
        assert make_pr(created_at=NOW).time_to_merge_seconds is None

    def test_time_to_first_review(self):
        pr = make_pr(created_at=NOW - timedelta(hours=5), first_review_at=NOW - timedelta(hours=3))
        assert pr.time_to_first_review_seconds == timedelta(hours=2).total_seconds()

    def test_time_to_first_review_none_without_review(self):
        assert make_pr(created_at=NOW).time_to_first_review_seconds is None

    def test_total_changed_lines(self):
        assert make_pr(additions=100, deletions=20).total_changed_lines == 120


class TestGitHubConnection:
    def test_missing_permissions(self):
        missing = GitHubConnection.missing_permissions({"contents", "metadata"})
        assert missing == {"issues", "pull_requests"}

    def test_no_missing_permissions(self):
        granted = {"contents", "issues", "pull_requests", "metadata", "actions"}
        assert GitHubConnection.missing_permissions(granted) == set()


class TestSyncJob:
    def make_job(self, mode=IndexingMode.PROJECT_INTELLIGENCE) -> SyncJob:
        job = SyncJob(id=uuid4(), repository_id=uuid4(), mode=mode)
        job.plan()
        return job

    def test_docs_only_plan_excludes_issues_and_files(self):
        steps = [s.step for s in self.make_job(IndexingMode.DOCS_ONLY).steps]
        assert SyncStep.ISSUES not in steps
        assert SyncStep.FILE_TREE not in steps
        assert SyncStep.DOCS in steps

    def test_code_metadata_plan_includes_file_tree(self):
        steps = [s.step for s in self.make_job(IndexingMode.CODE_METADATA).steps]
        assert SyncStep.FILE_TREE in steps
        assert SyncStep.ISSUES in steps

    def test_finish_fails_when_any_step_failed(self):
        job = self.make_job()
        job.start(NOW)
        job.record_step(SyncStep.DOCS, SyncStatus.SUCCEEDED, items=3)
        job.record_step(SyncStep.ISSUES, SyncStatus.FAILED, error="boom")
        job.finish(NOW)
        assert job.status is SyncStatus.FAILED
        assert [s.step for s in job.failed_steps] == [SyncStep.ISSUES]

    def test_finish_succeeds_when_all_steps_ok(self):
        job = self.make_job(IndexingMode.DOCS_ONLY)
        job.start(NOW)
        for result in job.steps:
            job.record_step(result.step, SyncStatus.SUCCEEDED)
        job.finish(NOW)
        assert job.status is SyncStatus.SUCCEEDED

    def test_record_unplanned_step_raises(self):
        job = self.make_job(IndexingMode.DOCS_ONLY)
        with pytest.raises(KeyError):
            job.record_step(SyncStep.FILE_TREE, SyncStatus.SUCCEEDED)


class TestSourceCodeSyncSteps:
    def test_source_code_step_only_for_code_modes(self):
        from app.domain.entities.sync_job import SyncJob
        from app.domain.value_objects.enums import IndexingMode, SyncStep

        def steps(mode):
            j = SyncJob(id=uuid4(), repository_id=uuid4(), mode=mode)
            j.plan()
            return [s.step for s in j.steps]

        assert SyncStep.SOURCE_CODE not in steps(IndexingMode.CODE_METADATA)
        cc = steps(IndexingMode.CODE_CONTEXT)
        assert SyncStep.SOURCE_CODE in cc
        # positioned after file_tree, before embeddings
        assert cc.index(SyncStep.SOURCE_CODE) > cc.index(SyncStep.FILE_TREE)
        assert cc.index(SyncStep.SOURCE_CODE) < cc.index(SyncStep.EMBEDDINGS)
        assert SyncStep.SOURCE_CODE in steps(IndexingMode.FULL_CONTEXT)
