# Per-organization authorization

## Why

Authorization is currently all-or-nothing: any caller with the `mnemosyne`
entitlement can read **every** indexed organization and private repository. For a
multi-team organization this is a data-boundary problem — a team-A agent can read
team-B's private code. This is the one hard blocker before rolling Mnemosyne out
beyond a single trusted team.

## What changes

Scope a caller to specific organizations via CyberdyneAuth **entitlement plans**:

- The bare `mnemosyne` entitlement (or `is_admin`, or a service token's audience)
  grants access to **all** indexed organizations — unchanged, backward compatible.
- A `mnemosyne:<org>` plan-qualified entitlement restricts the caller to that
  organization (multiple plans → the union). Org matching is case-insensitive.

Enforcement is **central**: a request-scoped allowed-orgs set is consulted at the
single choke point every read passes through — the repository store's `get`,
`get_by_full_name`, and `list_all`. A repository outside scope is treated as
**not found** (404 / omitted), so per-repo endpoints, org rollups, cross-repo
search, and the portfolio are all scoped by construction. Background sync (no
caller) is unrestricted.

## Impact

- `CallerIdentity.allowed_organizations(product_key)` derives the scope from entitlements.
- Request-scoped `allowed_orgs` contextvar, set by the REST entitled-caller
  dependency and by the MCP `auth()` gate.
- Repository store (Postgres + fakes) filter reads by the scope.
- auth spec: a per-organization scoping requirement.
