"""Boot-time settings validation: fail fast on missing/unsafe production config.

#68 (CWE-320) + #70 (CWE-1188): required secrets must be supplied in production.
#79 (CWE-918): the GitHub API base must be a public https host outside dev/test.
Dev/test tolerate empty/default secrets and internal API overrides.
"""

import pytest

from app.config import ConfigurationError, Settings


def _settings(**overrides) -> Settings:
    base: dict[str, object] = {
        "app_env": "production",
        "token_encryption_key": "fernet-key",
        "database_url": "postgresql+asyncpg://u:p@db:5432/x",
        "minio_secret_key": "minio-secret",
        "github_api_base_url": "https://api.github.com",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field, env_name",
    [
        ("token_encryption_key", "TOKEN_ENCRYPTION_KEY"),
        ("database_url", "DATABASE_URL"),
        ("minio_secret_key", "MINIO_SECRET_KEY"),
    ],
)
def test_production_missing_secret_fails_fast(field, env_name):
    settings = _settings(**{field: ""})
    with pytest.raises(ConfigurationError) as exc:
        settings.validate_runtime()
    assert env_name in str(exc.value)


def test_production_blank_secret_fails_fast():
    with pytest.raises(ConfigurationError):
        _settings(token_encryption_key="   ").validate_runtime()


def test_production_all_secrets_present_ok():
    _settings().validate_runtime()  # does not raise


@pytest.mark.parametrize("app_env", ["dev", "test"])
def test_dev_test_tolerate_empty_secrets(app_env):
    _settings(
        app_env=app_env,
        token_encryption_key="",
        database_url="",
        minio_secret_key="",
    ).validate_runtime()  # no error


def test_production_internal_github_api_base_rejected():
    with pytest.raises(ConfigurationError):
        _settings(github_api_base_url="https://10.0.0.10/api").validate_runtime()


def test_production_metadata_github_api_base_rejected():
    with pytest.raises(ConfigurationError):
        _settings(github_api_base_url="http://169.254.169.254/").validate_runtime()


def test_staging_internal_github_api_base_rejected():
    # #79: only dev/test may point the API base at internal hosts.
    with pytest.raises(ConfigurationError):
        _settings(
            app_env="staging",
            token_encryption_key="",  # staging isn't production; secrets optional
            database_url="",
            minio_secret_key="",
            github_api_base_url="https://192.168.0.1/api",
        ).validate_runtime()


def test_dev_internal_github_api_base_allowed():
    _settings(
        app_env="dev",
        github_api_base_url="http://localhost:8080",
    ).validate_runtime()  # BDD fixtures point here; no error
