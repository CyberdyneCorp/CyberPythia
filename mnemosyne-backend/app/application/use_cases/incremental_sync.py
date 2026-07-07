"""Incremental single-entity syncs for webhook events (spec: repository-sync)."""

from uuid import uuid4

from app.application.metrics_recompute import MetricsRecomputeService
from app.application.use_cases.github_connections import GitHubConnectionUseCases
from app.domain.entities.issue import Issue
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.ports.github_port import GitHubNotFoundError, GitHubPort
from app.domain.ports.persistence_ports import IssuePort, PullRequestPort, RepositoryPort
from app.domain.value_objects.enums import IssueState, PullRequestState


class IncrementalSyncUseCases:
    def __init__(
        self,
        repositories: RepositoryPort,
        issues: IssuePort,
        pull_requests: PullRequestPort,
        github: GitHubPort,
        connection_use_cases: GitHubConnectionUseCases,
        metrics: MetricsRecomputeService,
    ) -> None:
        self._repositories = repositories
        self._issues = issues
        self._pull_requests = pull_requests
        self._github = github
        self._connections = connection_use_cases
        self._metrics = metrics

    async def _enabled_repo(self, full_name: str) -> Repository | None:
        repo = await self._repositories.get_by_full_name(full_name)
        return repo if repo is not None and repo.enabled else None

    async def sync_issue(self, full_name: str, number: int) -> bool:
        repo = await self._enabled_repo(full_name)
        if repo is None:
            return False
        token = await self._connections.credential_for(repo.connection_id)
        try:
            data = await self._github.get_issue(token, full_name, number)
        except GitHubNotFoundError:
            return False
        if data.is_pull_request:  # a PR delivered on the issues surface
            return await self.sync_pull_request(full_name, number)
        existing = await self._issues.get_by_number(repo.id, number)
        await self._issues.save_many(
            [
                Issue(
                    id=existing.id if existing else uuid4(),
                    repository_id=repo.id,
                    github_issue_id=data.github_id,
                    number=data.number,
                    title=data.title,
                    body=data.body,
                    state=IssueState(data.state),
                    author=data.author,
                    labels=data.labels,
                    assignees=data.assignees,
                    milestone=data.milestone,
                    created_at=data.created_at,
                    updated_at=data.updated_at,
                    closed_at=data.closed_at,
                    comments_count=data.comments_count,
                )
            ]
        )
        await self._metrics.recompute(repo)
        return True

    async def sync_pull_request(self, full_name: str, number: int) -> bool:
        repo = await self._enabled_repo(full_name)
        if repo is None:
            return False
        token = await self._connections.credential_for(repo.connection_id)
        try:
            data = await self._github.get_pull_request(token, full_name, number)
        except GitHubNotFoundError:
            return False
        existing = await self._pull_requests.get_by_number(repo.id, number)
        await self._pull_requests.save_many(
            [
                PullRequest(
                    id=existing.id if existing else uuid4(),
                    repository_id=repo.id,
                    github_pr_id=data.github_id,
                    number=data.number,
                    title=data.title,
                    body=data.body,
                    state=PullRequestState(data.state),
                    merged=data.merged,
                    author=data.author,
                    reviewers=data.reviewers,
                    created_at=data.created_at,
                    updated_at=data.updated_at,
                    closed_at=data.closed_at,
                    merged_at=data.merged_at,
                    first_review_at=data.first_review_at,
                    changed_files=data.changed_files,
                    additions=data.additions,
                    deletions=data.deletions,
                    review_decision=data.review_decision,
                )
            ]
        )
        await self._metrics.recompute(repo)
        return True

    async def update_repository_metadata(self, full_name: str) -> bool:
        repo = await self._repositories.get_by_full_name(full_name)
        if repo is None or not repo.enabled:
            return False
        token = await self._connections.credential_for(repo.connection_id)
        try:
            data = await self._github.get_repository(token, full_name)
        except GitHubNotFoundError:
            return False
        repo.description = data.description
        repo.default_branch = data.default_branch
        repo.primary_language = data.primary_language
        repo.archived = data.archived
        repo.github_updated_at = data.updated_at
        await self._repositories.save(repo)
        return True

    async def remove_repository(self, full_name: str) -> bool:
        repo = await self._repositories.get_by_full_name(full_name)
        if repo is None:
            return False
        repo.disable()
        await self._repositories.save(repo)
        return True
