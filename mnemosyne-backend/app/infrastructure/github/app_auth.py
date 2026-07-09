"""GitHubAppAuth: app JWT -> short-lived installation access token (design D2)."""

import time

import httpx
import jwt

from app.domain.ports.github_app_port import AppManifestCredentials, GitHubAppError

API_BASE = "https://api.github.com"
JWT_TTL_SECONDS = 540  # 9 min (GitHub max is 10)
JWT_BACKDATE_SECONDS = 60  # clock-skew tolerance
REFRESH_MARGIN_SECONDS = 60  # re-mint this long before expiry


class GitHubAppAuth:
    def __init__(
        self, client: httpx.AsyncClient | None = None, base_url: str = API_BASE
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=15)
        self._base_url = base_url
        # installation_id -> (token, expires_at_epoch)
        self._cache: dict[str, tuple[str, float]] = {}

    def _app_jwt(self, app_id: str, private_key_pem: str) -> str:
        now = int(time.time())
        payload = {"iat": now - JWT_BACKDATE_SECONDS, "exp": now + JWT_TTL_SECONDS, "iss": app_id}
        try:
            return jwt.encode(payload, private_key_pem, algorithm="RS256")
        except Exception as exc:
            raise GitHubAppError(f"could not sign app JWT: {exc}") from exc

    async def installation_token(
        self, app_id: str, installation_id: str, private_key_pem: str
    ) -> str:
        cached = self._cache.get(installation_id)
        if cached is not None and time.time() < cached[1] - REFRESH_MARGIN_SECONDS:
            return cached[0]

        app_jwt = self._app_jwt(app_id, private_key_pem)
        try:
            response = await self._client.post(
                f"{self._base_url}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        except httpx.HTTPError as exc:
            raise GitHubAppError(f"installation token request failed: {exc}") from exc
        if response.status_code != 201:
            raise GitHubAppError(
                f"GitHub rejected the installation token request: {response.status_code}"
            )
        payload = response.json()
        token: str = payload["token"]
        expires_at = _parse_epoch(payload.get("expires_at"))
        self._cache[installation_id] = (token, expires_at)
        return token

    async def convert_manifest_code(self, code: str) -> AppManifestCredentials:
        try:
            response = await self._client.post(
                f"{self._base_url}/app-manifests/{code}/conversions",
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        except httpx.HTTPError as exc:
            raise GitHubAppError(f"manifest conversion request failed: {exc}") from exc
        if response.status_code != 201:
            raise GitHubAppError(
                f"GitHub rejected the manifest conversion: {response.status_code}"
            )
        p = response.json()
        try:
            return AppManifestCredentials(
                app_id=str(p["id"]),
                private_key_pem=p["pem"],
                webhook_secret=p.get("webhook_secret", ""),
                owner_login=p["owner"]["login"],
                html_url=p["html_url"],
                slug=p["slug"],
            )
        except (KeyError, TypeError) as exc:
            raise GitHubAppError(f"unexpected manifest conversion response: {exc}") from exc

    async def close(self) -> None:
        await self._client.aclose()


def _parse_epoch(value: str | None) -> float:
    if not value:
        return time.time() + 3600
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
