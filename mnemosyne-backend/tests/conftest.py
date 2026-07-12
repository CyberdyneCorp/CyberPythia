"""Global test fixtures: tests must be hermetic w.r.t. the developer's .env.

pydantic-settings gives real environment variables precedence over `.env`,
so pinning the authz config here shields every test from local overrides
(e.g. a production REQUIRED_ENTITLEMENT in mnemosyne-backend/.env).
"""

import pytest

from app.config import get_settings
from app.domain.services.org_scope import set_allowed_organizations


@pytest.fixture(autouse=True)
def _reset_org_scope():
    """Clear the request-scoped org boundary around every test (isolation)."""
    set_allowed_organizations(None)
    yield
    set_allowed_organizations(None)


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch):
    monkeypatch.setenv("REQUIRED_ENTITLEMENT", "mnemosyne")
    monkeypatch.setenv("SERVICE_AUDIENCE", "mnemosyne")
    monkeypatch.setenv("ADMIN_SCOPE", "mnemosyne:admin")
    monkeypatch.setenv("AUTH_VALIDATION_MODE", "jwks")
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://mnemosyne.coolify.cyberdynecorp.ai,http://localhost:5173,http://localhost:3000",
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
