"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(Exception):
    """A required setting is missing or unsafe for the current environment."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "staging", "production"] = "dev"
    app_name: str = "Mnemosyne"

    # Browser origins allowed to call the REST API (comma-separated)
    cors_allowed_origins: str = (
        "https://mnemosyne.coolify.cyberdynecorp.ai,"
        "http://localhost:5173,http://localhost:3000"
    )

    # Sensitive connection secrets default to empty so no working credential is
    # committed (#70, CWE-1188). Production must supply them (validated at boot in
    # `validate_runtime`); dev/test set them via compose env or the local .env.
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "mnemosyne"
    minio_secret_key: str = ""
    minio_bucket: str = "mnemosyne-artifacts"
    minio_secure: bool = False

    # CyberdyneAuth (design D1-D3)
    cyberdyneauth_issuer: str = "https://auth.backend.coolify.cyberdynecorp.ai"
    # `iss` claim of access/service JWTs (a logical name, unlike OIDC ID tokens)
    cyberdyneauth_token_issuer: str = "cyberdyne-auth"
    cyberdyneauth_jwks_url: str = ""  # derived from issuer when empty
    cyberdyneauth_client_id: str = ""  # mnemosyne-backend service client
    cyberdyneauth_client_secret: str = ""
    auth_validation_mode: Literal["jwks", "introspect"] = "jwks"
    auth_jwks_cache_ttl_seconds: int = 3600
    # Minimum interval between JWKS refetches triggered by an *unknown* kid, so a
    # pre-auth caller streaming random kids can force at most one outbound JWKS
    # GET per window instead of one per request (CWE-770). TTL-based refresh is
    # unaffected. Within the cooldown an unknown kid is treated as unknown.
    auth_jwks_min_refresh_seconds: int = 30
    # Force revocation-aware introspection on sensitive (admin) operations even
    # when the JWT embeds an entitlements claim, so a revoked-but-unexpired token
    # can no longer administer (CWE-613).
    auth_force_introspect_admin: bool = True
    # Users: entitlement product key (= the mnemosyne OAuth client's client_id).
    # Agents/services: token audience (CyberdyneAuth entitlements are user-only).
    required_entitlement: str = "mnemosyne"
    service_audience: str = "mnemosyne"
    admin_scope: str = "mnemosyne:admin"

    # DoS resilience: request rate limiting (spec: rest-api; CWE-770).
    # Limits are slowapi rate strings ("<count>/<period>"). Disable in tests.
    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"  # global per-caller default (all routes)
    rate_limit_llm: str = "20/minute"  # stricter bucket for cost-bearing LLM/embedding routes
    rate_limit_webhook: str = "60/minute"  # unauthenticated GitHub webhook receiver
    rate_limit_health: str = "120/minute"  # unauthenticated health check
    # Reverse proxies in front of the app (Coolify = 1). Unauthenticated traffic
    # is keyed on the client IP taken from the Nth-from-right X-Forwarded-For
    # entry; earlier entries are client-supplied and untrusted. 0 = ignore XFF
    # and key on the peer address (safe for a directly internet-facing deploy).
    # Requires uvicorn --proxy-headers (see docs/deploy-coolify.md); without a
    # correct value all forwarded traffic collapses onto the single proxy IP.
    rate_limit_trusted_proxy_hops: int = 1
    # Reject GitHub webhook payloads larger than this many bytes with 413 before
    # reading/parsing the body or verifying its signature (CWE-770).
    webhook_max_body_bytes: int = 1_048_576  # 1 MiB

    # GitHub credential encryption (design D6, spec github-connection)
    token_encryption_key: str = ""

    # GitHub API base URL — overridable so BDD suites can point at fixtures
    github_api_base_url: str = "https://api.github.com"
    # github.com base (App-creation page) — overridable for BDD fixtures
    github_web_base_url: str = "https://github.com"
    # Public base URLs (behind the proxy) used to build GitHub App manifest
    # webhook/redirect/setup URLs and the post-install return to the dashboard.
    public_api_base_url: str = "https://mnemosyne.backend.coolify.cyberdynecorp.ai"
    public_web_base_url: str = "https://mnemosyne.coolify.cyberdynecorp.ai"

    # MCP server bind port
    mcp_port: int = 8100

    # MCP one-click OAuth (FastMCP OAuthProxy bridging to CyberdyneAuth).
    # Off by default — ships dark; additive to API-key + bearer auth.
    mcp_oauth_enabled: bool = False
    mcp_oauth_public_base_url: str = ""  # public MCP origin, e.g. https://mnemosyne.mcp.<domain>
    mcp_oauth_client_id: str = ""  # CyberdyneAuth confidential client `mnemosyne-mcp`
    mcp_oauth_client_secret: str = ""
    mcp_oauth_redirect_path: str = "/auth/callback"
    # Where OAuthProxy persists DCR client registrations. Empty → a writable temp
    # dir (the container user has no usable $HOME). Point at a volume to persist.
    mcp_oauth_storage_dir: str = ""
    # Scopes advertised to clients + defaulted onto the upstream authorize request.
    # CyberdyneAuth requires a scope (min `openid`); `offline_access` yields refresh.
    mcp_oauth_scopes: str = "openid profile email offline_access"
    # Upstream endpoints — derived from the issuer when empty (see properties below)
    mcp_oauth_authorize_url: str = ""
    mcp_oauth_token_url: str = ""

    # Embeddings (design D7)
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    # Per-input char cap before embedding. text-embedding-3 accepts <= 8192
    # tokens; since a token is always >= 1 character, capping characters bounds
    # tokens. 16000 keeps realistic content (>=2 chars/token) safely under the
    # limit; a bulletproof retry truncates harder if the API still rejects it.
    embedding_max_input_chars: int = 16000

    # Apply Alembic migrations to head when the API starts (idempotent). Only the
    # API container triggers the FastAPI lifespan, so migrations run once there.
    run_migrations_on_boot: bool = True

    # Outbound alert delivery: POST each enabled org's daily attention digest to
    # this incoming-webhook URL (Slack-compatible). Empty = pull-only.
    alert_webhook_url: str = ""
    alert_digest_enabled: bool = True

    # Sync behavior
    stale_issue_days: int = 30
    stale_pr_days: int = 30
    sync_lock_ttl_seconds: int = 3600

    # Source-code indexing (Phase 3)
    source_size_cap_bytes: int = 512 * 1024
    code_window_lines: int = 80
    code_window_overlap: int = 10

    # Scheduled daily full sync (runs in the worker)
    scheduled_sync_enabled: bool = True
    scheduled_sync_hour: int = 3  # UTC hour, off-peak
    scheduled_sync_minute: int = 0

    # Scheduled discovery + auto-enable of newly-seen repos (runs before the daily sync)
    scheduled_discovery_enabled: bool = True
    auto_enable_new_repos: bool = True
    auto_enable_mode: str = "project_intelligence"
    auto_enable_archived: bool = False
    default_org_sync_enabled: bool = True  # a newly-discovered org syncs unless toggled off

    # Rate-limit resilience for the nightly fan-out
    scheduled_sync_stagger_seconds: float = 5.0  # defer between successive enqueues
    # Cap repos attempted per scheduled run (0 = all). Least-recently-synced go
    # first, so a large org spreads across runs instead of starving its tail when
    # the GitHub rate budget can't cover everything in one run.
    scheduled_sync_max_repos_per_run: int = 0

    # Delete metrics/readiness snapshots older than this many days on the daily
    # run, so the per-repo daily time-series don't grow unbounded (0 = keep all).
    history_retention_days: int = 365
    github_rate_limit_max_wait_seconds: int = 60  # cap; beyond this, fail fast + retry next run

    @property
    def jwks_url(self) -> str:
        return self.cyberdyneauth_jwks_url or f"{self.cyberdyneauth_issuer}/.well-known/jwks.json"

    @property
    def introspection_url(self) -> str:
        return f"{self.cyberdyneauth_issuer}/api/v1/auth/introspect"

    @property
    def token_url(self) -> str:
        return f"{self.cyberdyneauth_issuer}/api/v1/auth/oauth2/token"

    @property
    def mcp_oauth_upstream_authorize_url(self) -> str:
        return (
            self.mcp_oauth_authorize_url
            or f"{self.cyberdyneauth_issuer}/api/v1/auth/oauth2/authorize"
        )

    @property
    def mcp_oauth_upstream_token_url(self) -> str:
        return self.mcp_oauth_token_url or self.token_url

    def validate_runtime(self) -> None:
        """Fail fast at boot on missing/unsafe settings for this environment.

        In production, required secrets must be supplied (#68/#70/#798/#1188) and
        the GitHub API base must be a public https host (#79, CWE-918). Dev/test
        tolerate empty/default secrets and internal API overrides so the suites
        and local runs work without real credentials or a reachable GitHub.
        """
        # SSRF: the GitHub API base is followed with the bearer token, so an
        # internal override in a deployed environment is an SSRF vector. Only
        # dev/test may point it at fixtures/localhost.
        if self.app_env not in ("dev", "test"):
            from app.infrastructure.security.url_guard import (
                UnsafeUrlError,
                assert_public_https_url,
            )

            try:
                assert_public_https_url(self.github_api_base_url)
            except UnsafeUrlError as exc:
                raise ConfigurationError(
                    f"GITHUB_API_BASE_URL is not a safe public https URL: {exc}"
                ) from exc

        if self.app_env != "production":
            return
        missing = sorted(
            name
            for name, value in (
                ("TOKEN_ENCRYPTION_KEY", self.token_encryption_key),
                ("DATABASE_URL", self.database_url),
                ("MINIO_SECRET_KEY", self.minio_secret_key),
            )
            if not value.strip()
        )
        if missing:
            raise ConfigurationError(
                "missing required production secrets: " + ", ".join(missing)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
