"""Outbound port to GitHub. Adapters live in infrastructure/github."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GitHubTokenInfo:
    login: str
    owner_type: str  # "User" | "Organization"
    permissions: set[str]


@dataclass(frozen=True, slots=True)
class GitHubRepoData:
    github_id: int
    full_name: str
    description: str | None
    visibility: str
    default_branch: str
    primary_language: str | None
    archived: bool
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class GitHubFileData:
    path: str
    sha: str
    size: int
    is_binary: bool


@dataclass(frozen=True, slots=True)
class GitHubIssueData:
    github_id: int
    number: int
    title: str
    body: str | None
    state: str
    author: str | None
    labels: list[str]
    assignees: list[str]
    milestone: str | None
    created_at: datetime | None
    updated_at: datetime | None
    closed_at: datetime | None
    comments_count: int
    is_pull_request: bool


@dataclass(frozen=True, slots=True)
class GitHubPullRequestData:
    github_id: int
    number: int
    title: str
    body: str | None
    state: str
    merged: bool
    author: str | None
    reviewers: list[str]
    created_at: datetime | None
    updated_at: datetime | None
    closed_at: datetime | None
    merged_at: datetime | None
    first_review_at: datetime | None
    changed_files: int
    additions: int
    deletions: int
    review_decision: str | None


@dataclass(frozen=True, slots=True)
class GitHubMilestoneData:
    number: int
    title: str
    state: str
    due_on: datetime | None
    open_issues: int
    closed_issues: int
    updated_at: datetime | None


class GitHubAuthError(Exception):
    """Credential rejected by GitHub."""


class GitHubNotFoundError(Exception):
    pass


class GitHubRateLimitError(Exception):
    """Rate limited with a reset further out than the client's max wait — fail fast."""


class GitHubPort(Protocol):
    async def validate_token(self, token: str) -> GitHubTokenInfo: ...

    async def validate_installation_token(
        self, token: str, owner: str = ""
    ) -> GitHubTokenInfo: ...

    async def list_repositories(self, token: str) -> list[GitHubRepoData]: ...

    async def list_installation_repositories(
        self, token: str
    ) -> list[GitHubRepoData]: ...

    async def get_repository(self, token: str, full_name: str) -> GitHubRepoData: ...

    async def get_file_content(self, token: str, full_name: str, path: str) -> str: ...

    async def get_tree(self, token: str, full_name: str, branch: str) -> list[GitHubFileData]: ...

    async def list_issues(self, token: str, full_name: str) -> list[GitHubIssueData]: ...

    async def list_milestones(
        self, token: str, full_name: str
    ) -> list[GitHubMilestoneData]: ...

    async def has_releases(self, token: str, full_name: str) -> bool: ...

    async def vulnerability_summary(
        self, token: str, full_name: str
    ) -> dict[str, int] | None: ...

    async def list_pull_requests(
        self, token: str, full_name: str
    ) -> list[GitHubPullRequestData]: ...

    async def get_issue(
        self, token: str, full_name: str, number: int
    ) -> GitHubIssueData: ...

    async def get_pull_request(
        self, token: str, full_name: str, number: int
    ) -> GitHubPullRequestData: ...

    async def get_rate_limit(self, token: str) -> dict[str, int]: ...
