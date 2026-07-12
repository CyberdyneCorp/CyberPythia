"""Outbound alert delivery to a configured incoming-webhook URL (best-effort)."""

import logging
from typing import Any

import httpx

from app.infrastructure.security.url_guard import assert_public_https_url

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """POSTs a JSON payload to a configured URL. Slack-compatible (`text` field).

    Best-effort: a missing URL, timeout, or non-2xx never raises — it logs and
    returns False so callers (the daily run) are never failed by delivery.
    """

    def __init__(
        self,
        url: str | None,
        *,
        timeout_seconds: float = 10.0,
        allow_localhost: bool = False,
    ) -> None:
        # Validate the sink at construction so an SSRF target (e.g. the cloud
        # metadata endpoint or an internal service) is rejected before any
        # delivery is attempted (#78, CWE-918). Localhost is opt-in for dev.
        if url is not None:
            assert_public_https_url(url, allow_localhost=allow_localhost)
        self._url = url
        self._timeout = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def send(self, payload: dict[str, Any]) -> bool:
        if not self._url:
            return False
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
            return True
        except Exception:
            logger.warning("alert delivery failed", exc_info=True)
            return False
