"""Port for GitHub App installation-token minting (design D2)."""

from dataclasses import dataclass
from typing import Protocol


class GitHubAppError(Exception):
    """App credentials rejected, or the installation token could not be minted."""


@dataclass(frozen=True, slots=True)
class AppManifestCredentials:
    """Credentials returned when a GitHub App is created from a manifest."""

    app_id: str
    private_key_pem: str
    webhook_secret: str
    owner_login: str
    html_url: str
    slug: str


class GitHubAppPort(Protocol):
    async def installation_token(
        self, app_id: str, installation_id: str, private_key_pem: str
    ) -> str:
        """Mint (or return a cached) short-lived installation access token."""
        ...

    async def convert_manifest_code(self, code: str) -> AppManifestCredentials:
        """Exchange a one-time App-manifest code for the new App's credentials."""
        ...
