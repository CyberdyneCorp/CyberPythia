"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "staging", "production"] = "dev"
    app_name: str = "Mnemosyne"

    database_url: str = "postgresql+asyncpg://mnemosyne:mnemosyne@localhost:5433/mnemosyne"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "mnemosyne"
    minio_secret_key: str = "mnemosyne-secret"
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
    # Users: entitlement product key (= the mnemosyne OAuth client's client_id).
    # Agents/services: token audience (CyberdyneAuth entitlements are user-only).
    required_entitlement: str = "mnemosyne"
    service_audience: str = "mnemosyne"
    admin_scope: str = "mnemosyne:admin"

    # GitHub credential encryption (design D6, spec github-connection)
    token_encryption_key: str = ""

    # GitHub API base URL — overridable so BDD suites can point at fixtures
    github_api_base_url: str = "https://api.github.com"

    # MCP server bind port
    mcp_port: int = 8100

    # Embeddings (design D7)
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Sync behavior
    stale_issue_days: int = 30
    stale_pr_days: int = 30
    sync_lock_ttl_seconds: int = 3600

    @property
    def jwks_url(self) -> str:
        return self.cyberdyneauth_jwks_url or f"{self.cyberdyneauth_issuer}/.well-known/jwks.json"

    @property
    def introspection_url(self) -> str:
        return f"{self.cyberdyneauth_issuer}/api/v1/auth/introspect"

    @property
    def token_url(self) -> str:
        return f"{self.cyberdyneauth_issuer}/api/v1/auth/oauth2/token"


@lru_cache
def get_settings() -> Settings:
    return Settings()
