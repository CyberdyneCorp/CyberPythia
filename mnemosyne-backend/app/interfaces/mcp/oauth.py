"""MCP one-click OAuth wiring (spec: mcp-interface, auth).

A FastMCP ``OAuthProxy`` that serves the OAuth surface (protected-resource
metadata, DCR, authorize/token) to clients which self-register — claude.ai,
Claude Desktop — and bridges the authorization-code + PKCE flow to CyberdyneAuth,
which supports auth-code but not DCR.

The proxy's token verifier delegates to the shared ``auth_port`` composite, so
the exact same credentials keep working alongside OAuth: Mnemosyne API keys
(``mnem_…``), CyberdyneAuth service tokens, and user tokens. The resolved
``CallerIdentity`` is stashed in the access-token claims so tools authorize
without a second round-trip.
"""

from __future__ import annotations

import logging

from fastmcp.server.auth.auth import AccessToken, TokenVerifier
from fastmcp.server.auth.oauth_proxy import OAuthProxy

from app.config import Settings
from app.domain.ports.auth_port import AuthPort, AuthUnavailableError, TokenInvalidError
from app.domain.value_objects.identity import CallerIdentity

logger = logging.getLogger(__name__)

# Key under which the resolved CallerIdentity is stored on the AccessToken claims.
CALLER_CLAIM = "mnemosyne_caller"


class CompositeTokenVerifier(TokenVerifier):
    """Validate any bearer (API key or CyberdyneAuth token) via ``auth_port``.

    Returns ``None`` (→ 401) for invalid, unreachable-auth, or unentitled tokens
    so the transport rejects them uniformly; a valid + entitled caller yields an
    ``AccessToken`` carrying the ``CallerIdentity`` in its claims.
    """

    def __init__(
        self, auth_port: AuthPort, *, required_entitlement: str, service_audience: str
    ) -> None:
        super().__init__()
        self._auth = auth_port
        self._entitlement = required_entitlement
        self._audience = service_audience

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            caller = await self._auth.verify(token)
        except (TokenInvalidError, AuthUnavailableError):
            return None
        if not caller.can_access(self._entitlement, self._audience):
            return None
        return AccessToken(
            token=token,
            client_id=caller.client_id or caller.subject,
            scopes=sorted(caller.scopes),
            subject=caller.subject,
            claims={CALLER_CLAIM: caller},
        )


def caller_from_access_token(access: AccessToken | None) -> CallerIdentity | None:
    """Recover the CallerIdentity stashed by CompositeTokenVerifier, if present."""
    if access is None:
        return None
    caller = access.claims.get(CALLER_CLAIM)
    return caller if isinstance(caller, CallerIdentity) else None


def build_oauth_proxy(auth_port: AuthPort, settings: Settings) -> OAuthProxy:
    """Construct the OAuthProxy from settings. Caller ensures OAuth is enabled."""
    if not settings.mcp_oauth_public_base_url:
        raise ValueError("mcp_oauth_public_base_url is required when MCP OAuth is enabled")
    if not settings.mcp_oauth_client_id or not settings.mcp_oauth_client_secret:
        raise ValueError("mcp_oauth_client_id/secret are required when MCP OAuth is enabled")

    verifier = CompositeTokenVerifier(
        auth_port,
        required_entitlement=settings.required_entitlement,
        service_audience=settings.service_audience,
    )
    return OAuthProxy(
        upstream_authorization_endpoint=settings.mcp_oauth_upstream_authorize_url,
        upstream_token_endpoint=settings.mcp_oauth_upstream_token_url,
        upstream_client_id=settings.mcp_oauth_client_id,
        upstream_client_secret=settings.mcp_oauth_client_secret,
        token_verifier=verifier,
        base_url=settings.mcp_oauth_public_base_url,
        redirect_path=settings.mcp_oauth_redirect_path,
        # User tokens authorize via the `mnemosyne` entitlement (introspection),
        # not an audience — so no resource/audience is forwarded upstream.
        forward_resource=False,
    )
