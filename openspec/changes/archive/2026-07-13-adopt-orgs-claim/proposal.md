# Adopt the CyberdyneAuth `orgs` authorization claim

## Why

Per-organization scoping currently derives a caller's accessible organizations
from the **entitlement plan qualifier** (`product_key:<org>`) — an overload of a
field that actually denotes a billing plan (CyberPythia#77 / FINDING-026). It is
ambiguous (a real plan like `mnemosyne:premium` is misread as an org) and cannot
represent a user authorized across several organizations.

CyberdyneAuth shipped a dedicated authorization claim (CyberdyneAuth#104, their
PR #105, deployed): access tokens and introspection now carry
`orgs: [{id, short_name, github_login}]` for the caller's **active** memberships.
`github_login` is the external key resource servers match against, kept distinct
from `short_name`.

This change makes Mnemosyne read that claim as the authoritative source of a
caller's organization scope, removing the plan-qualifier overload.

## What Changes

- `CallerIdentity` gains `authorized_org_logins: frozenset[str] | None` — the
  parsed `orgs` claim as GitHub org logins (lower-cased). `None` = claim absent.
- The token adapter parses `orgs` from both the JWKS and introspection claim sets.
- `allowed_organizations()` prefers the claim when present: the caller is
  restricted to exactly those logins; a present-but-empty claim grants **no**
  organizations (fail-closed); admins remain unrestricted (policy).
- When the claim is absent (legacy pre-`orgs` tokens, service tokens, and
  Mnemosyne API keys whose scope is encoded via `product_key:<org>` entitlements,
  #64) the existing plan-qualified-entitlement derivation is kept as a
  backward-compatible fallback.

## Consumer contract (from CyberdyneAuth#104)

- Key on `orgs[].github_login` for `is_organization_allowed(owner)` vs a repo's
  `owner/name`. A null `github_login` (org not yet mapped to GitHub) simply does
  not match — correct.
- **Absent ≠ empty**: a missing `orgs` key is a legacy token (fallback applies);
  an empty list means "authorized for no orgs".
- The claim reports real memberships regardless of `is_admin`; treating admins as
  unrestricted is Mnemosyne's policy.
- Freshness: membership changes take effect on the next token refresh;
  introspection is real-time.

## Non-goals

- Multi-org **entitlement** inheritance (entitlements still inherit from the
  primary org only, by CyberdyneAuth design).
- Removing the API-key `product_key:<org>` encoding (#64) — it stays as the
  fallback path for keys, which do not carry the claim.
