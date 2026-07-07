"""Enumerated value objects shared across the domain."""

from enum import StrEnum


class RepositoryVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"


class IndexingMode(StrEnum):
    """What a repository sync is allowed to capture (spec: repository-sync).

    Modes are cumulative: each includes everything the previous one captures.
    """

    DOCS_ONLY = "docs_only"
    PROJECT_INTELLIGENCE = "project_intelligence"
    CODE_METADATA = "code_metadata"

    @property
    def includes_issues_and_prs(self) -> bool:
        return self in (IndexingMode.PROJECT_INTELLIGENCE, IndexingMode.CODE_METADATA)

    @property
    def includes_file_tree(self) -> bool:
        return self is IndexingMode.CODE_METADATA


class DocumentType(StrEnum):
    README = "README"
    DOCS = "DOCS"
    OPENSPEC = "OPENSPEC"
    ARCHITECTURE = "ARCHITECTURE"
    SECURITY = "SECURITY"
    CHANGELOG = "CHANGELOG"
    CONTRIBUTING = "CONTRIBUTING"
    ROADMAP = "ROADMAP"
    GENERIC_MARKDOWN = "GENERIC_MARKDOWN"


class IssueState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class PullRequestState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class SyncStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SyncStep(StrEnum):
    METADATA = "metadata"
    DOCS = "docs"
    OPENSPEC = "openspec"
    ISSUES = "issues"
    PULL_REQUESTS = "pull_requests"
    FILE_TREE = "file_tree"
    EMBEDDINGS = "embeddings"
    METRICS = "metrics"


class EmbeddingStatus(StrEnum):
    PENDING = "pending"
    EMBEDDED = "embedded"
    SKIPPED = "skipped"


class OpenSpecStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


class ConnectionStatus(StrEnum):
    ACTIVE = "active"
    BROKEN = "broken"
    DISABLED = "disabled"
