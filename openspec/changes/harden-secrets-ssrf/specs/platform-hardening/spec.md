# platform-hardening Specification

## ADDED Requirements

### Requirement: Fail-fast secret configuration

The system SHALL validate required secrets at startup (container build), not
lazily on first use. Sensitive settings (`DATABASE_URL`, `MINIO_SECRET_KEY`,
`TOKEN_ENCRYPTION_KEY`) SHALL default to empty so no working credential is
committed to source (CWE-1188, CWE-798). When `app_env` is `production` and any of
these is unset or blank, startup SHALL fail with a configuration error naming the
missing setting. Outside production (`dev` / `test` / `staging`) the system SHALL
tolerate empty or default secrets so local runs and test suites work without real
credentials. Committed compose/deployment files SHALL NOT inline working datastore
passwords; they SHALL reference environment variables resolved from an untracked
`.env`, with an `.env.example` documenting them.

#### Scenario: Production boot fails on a missing secret
- **WHEN** the app is built with `app_env=production` and an empty `TOKEN_ENCRYPTION_KEY`, `DATABASE_URL`, or `MINIO_SECRET_KEY`
- **THEN** startup SHALL raise a configuration error identifying the missing secret

#### Scenario: Dev and test tolerate empty secrets
- **WHEN** the app is built with `app_env` of `dev` or `test` and empty sensitive secrets
- **THEN** startup SHALL succeed without a configuration error

#### Scenario: No working credential committed
- **WHEN** the committed configuration defaults and compose files are inspected
- **THEN** they SHALL contain no working datastore password, only empty defaults or environment-variable references documented in `.env.example`

### Requirement: Key separation for signed state

The system SHALL derive the HMAC key used to sign stateless CSRF `state` tokens
from `TOKEN_ENCRYPTION_KEY` via HKDF-SHA256 with a fixed info label, rather than
reusing the Fernet encryption key directly (CWE-320). The derived key SHALL be
distinct from the encryption key and deterministic for a given root key, and
signed-state tokens SHALL continue to sign and verify under it. Derivation SHALL
succeed even with an empty root key so dev/test work without a configured secret.

#### Scenario: State key is distinct from the encryption key
- **WHEN** the signed-state secret is derived from a `TOKEN_ENCRYPTION_KEY`
- **THEN** the derived secret SHALL differ from the encryption key

#### Scenario: Signed state round-trips under the derived key
- **WHEN** a `state` token is signed and later verified using the derived secret
- **THEN** verification SHALL succeed and return the original payload

### Requirement: SSRF-safe outbound URLs

The system SHALL validate externally influenced or configured outbound URLs
through a single shared host guard before sending a request or the bearer token
(CWE-918). The guard SHALL reject non-https URLs and hosts that are — or resolve
to — loopback, link-local, private (RFC1918), or otherwise non-public addresses,
with an opt-in localhost exception permitted only in dev/test. GitHub API
pagination SHALL follow a `Link: rel=next` URL only when it is same-origin (scheme,
host, and port) with the configured API base; an off-allowlist link SHALL NOT be
followed and the bearer token SHALL NOT be sent to it. The configured alert
webhook URL SHALL be validated at construction, and the configured
`github_api_base_url` SHALL be validated at startup outside dev/test.

#### Scenario: Pagination link to another or internal host is not followed
- **WHEN** an upstream response's `Link: rel=next` points at a different or internal host
- **THEN** the client SHALL stop paginating, SHALL NOT request that URL, and SHALL NOT send the bearer token to it

#### Scenario: Internal alert webhook rejected
- **WHEN** an alert webhook URL targets loopback, link-local (e.g. the cloud metadata endpoint), or an RFC1918 host, or is not https
- **THEN** construction SHALL fail rather than deliver to it (unless a dev/test localhost exception applies)

#### Scenario: Internal GitHub API base rejected in production
- **WHEN** `github_api_base_url` is overridden to an internal or non-https host and `app_env` is not `dev` or `test`
- **THEN** startup SHALL fail with a configuration error

#### Scenario: Dev/test may point at fixtures
- **WHEN** `app_env` is `dev` or `test` and `github_api_base_url` targets localhost or an internal fixture host
- **THEN** startup SHALL succeed so BDD suites can run against fixtures
