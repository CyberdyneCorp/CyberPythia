"""Port for GitHub App installation-token minting (design D2)."""

from typing import Protocol


class GitHubAppError(Exception):
    """App credentials rejected, or the installation token could not be minted."""


class GitHubAppPort(Protocol):
    async def installation_token(
        self, app_id: str, installation_id: str, private_key_pem: str
    ) -> str:
        """Mint (or return a cached) short-lived installation access token."""
        ...
