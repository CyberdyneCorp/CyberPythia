# Tasks

## 1. Domain
- [x] 1.1 Add `ApiKey` entity (`app/domain/entities/api_key.py`) with `is_valid(now)`
- [x] 1.2 Add `ApiKeyPort` protocol to `persistence_ports.py` (save, get_by_hash, list_all, revoke)

## 2. Infrastructure
- [x] 2.1 Add `app/domain/services/api_key_factory.py` — prefix, secret generation, SHA-256 hashing, display prefix
- [x] 2.2 Add `ApiKeyRow` model + migration `0007_api_keys.py`
- [x] 2.3 Add `PostgresApiKeyRepository` in `repositories/misc.py`
- [x] 2.4 Add `ApiKeyAuthAdapter` (`app/infrastructure/auth/api_key_auth.py`) wrapping the CyberdyneAuth adapter

## 3. Application
- [x] 3.1 Add `ApiKeyUseCases` (create → plaintext once, list, revoke)

## 4. Composition
- [x] 4.1 Wire `api_keys` repo, `cyberdyne_auth`, and composite `auth_port` in `composition.py`

## 5. REST interface
- [x] 5.1 Add request/response schemas
- [x] 5.2 Add `api_keys` router (POST create / GET list / DELETE revoke), admin-only, audited
- [x] 5.3 Register router in `main.py`

## 6. Web UI
- [x] 6.1 Add `ApiKey` / `ApiKeyCreated` models + `ApiKeysApi` client + context wiring
- [x] 6.2 Add key state + create/list/revoke methods to `ConnectionsViewModel`
- [x] 6.3 Add "API keys" panel to the Connections page (generate form, one-time reveal, list + revoke)

## 7. Tests
- [x] 7.1 Unit: `ApiKeyAuthAdapter` (valid / unknown / expired / revoked / non-mnem delegates / not admin)
- [x] 7.2 Unit: `ApiKeyUseCases` (create returns plaintext + stores hash not plaintext; list metadata; revoke)
- [x] 7.3 Unit: REST endpoints (create/list/revoke, non-admin 403, plaintext once)
- [x] 7.4 Integration: `PostgresApiKeyRepository` round-trip
- [x] 7.5 Web: `ConnectionsViewModel` key methods

## 8. Docs
- [x] 8.1 Update `docs/auth-integration.md` and `docs/mcp-consumers.md` with the API-key path
