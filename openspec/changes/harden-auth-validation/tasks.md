# Tasks

- [x] 1. Add `auth_jwks_min_refresh_seconds` and `auth_force_introspect_admin` to `app/config.py`
- [x] 2. #57: bound unknown-`kid` JWKS refetch with a min-refresh cooldown in `JwksVerifier._get_key`
- [x] 3. #65: validate `aud` after local decode (reject a present, mismatched audience; allow missing)
- [x] 4. #66: add `force_introspection` to `AuthPort.verify`, `CyberdyneAuthAdapter`, and `ApiKeyAuthAdapter`
- [x] 5. #66: re-verify through introspection on the admin-gating dependency (`get_admin_caller`)
- [x] 6. #63: add `is_read_only` to `CallerIdentity`; set it on API-key callers
- [x] 7. #63: add `WriterCaller` dependency; gate REST memory create/delete (repo + org) on it
- [x] 8. #63: gate mutating MCP tools (`mnemosyne_remember`, `mnemosyne_forget`) on a non-read-only caller
- [x] 9. #62: resolve the repo via org-scoped `use_cases.get(repo_id)` before fetching the document in `get_doc`
- [x] 10. Regression tests for all five findings (fail without the fix, pass with it)
- [x] 11. ruff, mypy, unit + persistence-integration suites green
