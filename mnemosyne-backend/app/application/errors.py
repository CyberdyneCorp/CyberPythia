"""Application-level errors mapped to API status codes by the interface layer."""


class ApplicationError(Exception):
    pass


class InvalidCredentialError(ApplicationError):
    """GitHub rejected the credential; nothing was persisted."""


class MissingPermissionsError(ApplicationError):
    def __init__(self, missing: set[str]):
        self.missing = sorted(missing)
        super().__init__(f"credential is missing required permissions: {', '.join(self.missing)}")


class UnknownResourceError(ApplicationError):
    pass


class RepositoryNotSyncedError(ApplicationError):
    """Operation requires at least one completed sync (spec: context-packs)."""


class SyncAlreadyRunningError(ApplicationError):
    """A sync is already running for this repository (spec: repository-sync)."""


class SourceNotIndexedError(ApplicationError):
    """Repository is not indexed for source code (mode below code_context)."""


class ContentUnavailableError(ApplicationError):
    """Requested file content was not captured (wrong mode, ignored, quarantined…)."""
