# Tasks

## #76 — Fail-closed org scope
- [x] 1. Add the `UNSET` sentinel + third state to `org_scope`; default the
      contextvar to `UNSET`; `is_organization_allowed` returns `False` under
      `UNSET`. Add `set_unrestricted()`, `reset_org_scope()`, `is_unrestricted()`
- [x] 2. Repoint `cross_repo` / `memory` "is unrestricted?" checks to
      `is_unrestricted()` (fail-closed under `UNSET`)
- [x] 3. Set the caller's boundary in `get_current_caller`, not only the entitled
      dependency (FINDING-025)
- [x] 4. Call `set_unrestricted()` at every off-request all-org entrypoint:
      `sync_repository`, `delete_connection`, `scheduled_full_sync`, and
      `ProcessWebhookDelivery.process`
- [x] 5. Tests: `UNSET` denies all; worker/webhook jobs reach all orgs from the
      fail-closed default; restricted denied cross-org; unrestricted/admin
      allowed; reset between requests

## #75 — Central MCP authentication
- [x] 6. Add a FastMCP middleware that authenticates + org-scopes every tool
      call and rejects read-only credentials on mutating tools
- [x] 7. Tests: a tool with no in-body `auth()` is still rejected when
      unauthenticated and org-scoped by the middleware

## #64 — Org-scoped API keys
- [x] 8. Add `allowed_organizations` to the `ApiKey` entity + a nullable column
      (`ApiKeyRow`) and Alembic migration `0010` (JSON/JSONB, `NULL` = all orgs)
- [x] 9. Encode the key's org boundary through the same entitlement mechanism as
      user tokens in `ApiKeyAuthAdapter` (no parallel path)
- [x] 10. Accept an optional org list on the create endpoint/use-case; normalise
      to lower-case; empty → `NULL`; echo it back in the response
- [x] 11. Tests: org-scoped key denied cross-org repos, allowed its own org;
      unscoped key unrestricted; use-case normalisation; column round-trips;
      migration upgrades + downgrades cleanly

## #77 — Org-scope claim disambiguation
- [x] 12. Deferred: needs a CyberdyneAuth authorization-org claim. Documented in
      the proposal + PR body; current entitlement-based derivation retained
