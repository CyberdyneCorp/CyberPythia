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
    CODE_CONTEXT = "code_context"
    FULL_CONTEXT = "full_context"

    @property
    def includes_issues_and_prs(self) -> bool:
        return self in (
            IndexingMode.PROJECT_INTELLIGENCE,
            IndexingMode.CODE_METADATA,
            IndexingMode.CODE_CONTEXT,
            IndexingMode.FULL_CONTEXT,
        )

    @property
    def includes_file_tree(self) -> bool:
        return self in (
            IndexingMode.CODE_METADATA,
            IndexingMode.CODE_CONTEXT,
            IndexingMode.FULL_CONTEXT,
        )

    @property
    def includes_source_code(self) -> bool:
        return self in (IndexingMode.CODE_CONTEXT, IndexingMode.FULL_CONTEXT)


class ChunkType(StrEnum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    MODULE = "module"
    WINDOW = "window"  # fallback for unsupported languages / oversized bodies


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
    SOURCE_CODE = "source_code"
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


class ConnectionKind(StrEnum):
    PAT = "pat"
    GITHUB_APP = "github_app"


class WebhookIntent(StrEnum):
    SYNC_REPOSITORY = "sync_repository"
    SYNC_ISSUE = "sync_issue"
    SYNC_PULL_REQUEST = "sync_pull_request"
    UPDATE_REPOSITORY = "update_repository"
    REMOVE_REPOSITORY = "remove_repository"
    RECONCILE_INSTALLATION = "reconcile_installation"
    IGNORE = "ignore"
