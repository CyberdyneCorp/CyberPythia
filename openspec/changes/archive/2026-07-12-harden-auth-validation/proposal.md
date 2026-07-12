# Harden token validation, document access scope, and API-key capabilities

## Why

Five security findings in the auth/authz layer:

- **#57 (CWE-770, JWKS DoS amplification)** — `JwksVerifier._get_key` refetches
  the JWKS on every unknown `kid`. The `kid` is read from the *unverified* header
  before signature validation, so a pre-auth attacker can stream random kids and
  force one outbound JWKS GET per request, amplifying load on the auth plane.
- **#65 (CWE-287, missing audience validation)** — local JWKS decode passes
  `verify_aud=False` unconditionally, so a token minted for a *different*
  audience is accepted as long as its signature/issuer/expiry are valid.
- **#66 (CWE-613, revocation bypass on admin ops)** — in `jwks` mode a JWT that
  embeds an `entitlements` claim skips the revocation-aware introspection path,
  so a revoked-but-unexpired token keeps working — including for sensitive admin
  operations.
- **#62 (CWE-639/BOLA, cross-org document read)** — `GET /repos/{repo_id}/docs/{doc_id}`
  fetches the document directly and only checks `doc.repository_id == repo_id`,
  skipping the org-scoped `use_cases.get(repo_id)` every sibling route uses. A
  caller scoped to org A can read a document of an out-of-scope repo in org B.
- **#63 (CWE-269, read-only key can mutate)** — Mnemosyne API keys are documented
  as read/query only but authorize on the `mnemosyne` entitlement alone, so a key
  can create/delete memories via the MCP `mnemosyne_remember`/`mnemosyne_forget`
  tools and the REST memory-write endpoints.

## What changes

- **Bounded unknown-`kid` refresh (#57):** add `AUTH_JWKS_MIN_REFRESH_SECONDS`
  (default 30). An unknown `kid` triggers at most one JWKS refetch per window;
  within the cooldown an unknown `kid` is treated as unknown. The normal
  TTL-based refresh is unchanged.
- **Audience validation (#65):** after local decode, a token that carries an
  `aud` claim MUST include the configured `SERVICE_AUDIENCE`, else it is
  rejected. A missing/empty `aud` (user tokens) is still accepted.
- **Force introspection on sensitive ops (#66):** add
  `AUTH_FORCE_INTROSPECT_ADMIN` (default true) and a `force_introspection`
  parameter on `AuthPort.verify`. The admin-gating dependency re-verifies the
  token through the revocation-aware introspection path regardless of embedded
  entitlements; a revoked token is rejected.
- **Org-scoped document access (#62):** `get_doc` resolves the repo through the
  org-scoped `use_cases.get(repo_id)` first (which 404s for out-of-scope repos)
  before fetching the document.
- **Read-only credential capability (#63):** add `is_read_only` to
  `CallerIdentity` (true for API keys). All mutating MCP tools
  (`mnemosyne_remember`, `mnemosyne_forget`) and REST memory write/delete
  endpoints reject read-only callers; reads still work.

## Impact

- `app/config.py`: `auth_jwks_min_refresh_seconds`, `auth_force_introspect_admin`.
- `app/infrastructure/auth/cyberdyne_auth.py`: cooldown, audience check,
  `force_introspection` on the adapter.
- `app/domain/ports/auth_port.py`: `verify(..., force_introspection=False)`.
- `app/domain/value_objects/identity.py`: `is_read_only`.
- `app/infrastructure/auth/api_key_auth.py`: mark API-key callers read-only.
- `app/interfaces/api/security.py`: `WriterCaller` dependency; admin path forces
  introspection.
- `app/interfaces/api/routers/{repositories,intelligence}.py`: org-scoped
  `get_doc`; memory write/delete gated on `WriterCaller`.
- `app/interfaces/mcp/server.py`: mutating tools gated on a non-read-only caller.
