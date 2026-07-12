# Harden the authorization structure: fail-closed org scope, central MCP auth, org-scoped API keys

## Why

Three structural authorization weaknesses remain after the per-organization
boundary (`add-per-organization`) and memory authz (`add-memory-org-authz`) work:

- **Fail-open org-scope default (#76, CWE-284).** The request-scoped org boundary
  defaults to `None` = *unrestricted*. Any entrypoint that forgets to set the
  scope therefore sees **every** organization. The boundary is fail-open: an
  omission leaks cross-org data rather than denying it. Every legitimate all-org
  entrypoint (worker jobs, webhook processing) relies on this implicit default,
  so the default cannot be tightened without first making those callers set the
  boundary explicitly. FINDING-025 additionally notes that only the *entitled*
  HTTP dependency sets the scope, not the base authenticated dependency.
- **MCP single-point-of-auth omission (#75, CWE-1188).** Every MCP tool must
  remember to call `auth()` / `auth_write()` itself. A newly added tool that
  forgets is unauthenticated, and — once the org scope is fail-closed — silently
  deny-by-default rather than fail loudly. Authentication is not enforced at a
  single choke point.
- **API keys are unrestricted across all orgs (#64, CWE-284).** Every `mnem_`
  key can read every organization. There is no way to issue a key limited to a
  tenant.

An informational item (#77) observes that org scoping overloads the entitlement
*plan* qualifier (`product_key:<plan>`) as an *organization* name.

## What changes

- **Fail-closed org scope (#76).** The org-scope contextvar gains a third state:
  `UNSET` (deny-all) becomes the default, distinct from `None` (unrestricted) and
  a restricted `frozenset`. `is_organization_allowed()` returns `False` under
  `UNSET`. A new `set_unrestricted()` is called explicitly at every legitimate
  all-org entrypoint — every worker job (`sync_repository`, `delete_connection`,
  `scheduled_full_sync`, and the discovery it nests) and webhook processing
  (`ProcessWebhookDelivery.process`). The base HTTP dependency
  (`get_current_caller`) now sets the caller's boundary (FINDING-025), not only
  the entitled dependency. Admin/service HTTP callers stay unrestricted via their
  identity (`allowed_organizations` → `None`).
- **Central MCP authentication (#75).** A FastMCP middleware authenticates and
  org-scopes **every** tool call before the tool body runs, and rejects
  read-only credentials on the mutating tools. A newly added tool can no longer
  ship unauthenticated. The per-tool `auth()` calls remain (some tools use the
  returned caller) but are no longer the sole line of defence.
- **Org-scoped API keys (#64).** `ApiKey` gains an optional
  `allowed_organizations` (list, nullable column via a new Alembic migration;
  `NULL` = unrestricted, backward compatible). The create endpoint accepts an
  optional org list (normalised to lower-case; empty → `NULL`). The API-key auth
  adapter encodes the boundary through the **same** entitlement mechanism as user
  tokens (`entitlement:<org>`), so the existing org-scope contextvar restricts
  the key with no parallel authz path.

Non-goals: **#77 is deferred.** A correct disambiguation needs a token claim
CyberdyneAuth does not emit today (see Impact); guessing risks breaking the
Wave 1 memory authz and #62 scoping. Current entitlement-based derivation is
retained unchanged.

## Impact

- Affected specs: `auth` (org scoping becomes fail-closed and covers API keys;
  MCP tools authenticate through a central choke point).
- Affected code: `app/domain/services/org_scope.py`,
  `app/interfaces/api/security.py`, `app/interfaces/mcp/server.py`,
  `app/infrastructure/queue/worker.py`,
  `app/application/use_cases/process_webhook.py`,
  `app/domain/entities/api_key.py`,
  `app/infrastructure/auth/api_key_auth.py`,
  `app/application/use_cases/api_keys.py`,
  `app/interfaces/api/routers/api_keys.py`,
  `app/interfaces/api/schemas/schemas.py`,
  `app/infrastructure/persistence/models.py`,
  `app/infrastructure/persistence/repositories/misc.py`,
  `app/application/use_cases/cross_repo.py`,
  `app/application/use_cases/memory.py`, and
  `migrations/versions/0010_api_key_org_scope.py`.
- Security: closes fail-open org scope (#76), unauthenticated-tool risk (#75),
  and unrestricted API keys (#64). No behavior change for admin/service callers,
  the worker, or existing (unscoped) API keys.

### #77 deferral — required CyberdyneAuth change

CyberdyneAuth user access tokens carry `entitlements` (list of
`product_key[:plan]`), a single-org `org` claim (`{id, short_name}`), and
`is_admin` — there is **no** claim enumerating the organizations a user is
*authorized* to access. The current code overloads the entitlement plan
qualifier as the org list. A clean fix requires CyberdyneAuth to emit a dedicated
authorization claim (e.g. `orgs: ["<short_name>", …]` of accessible org
short-names, distinct from the subscription plan). Until then, changing the
derivation would either restrict every non-admin user to their single `org`
short-name (breaking multi-org users and the #62 / Wave 1 tests) or invent a
claim. Tenant-isolation correctness outranks closing an informational item, so
#77 is left as-is and documented here.
