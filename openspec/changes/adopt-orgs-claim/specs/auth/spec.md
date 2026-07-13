# auth (delta)

## MODIFIED Requirements

### Requirement: Per-organization access scoping

The system SHALL maintain a request/tool-scoped organization boundary with three
states: **unset** (deny-all), **unrestricted** (all organizations), and a
restricted set of organizations. The boundary SHALL default to **unset**: with no
boundary established, every organization SHALL be treated as inaccessible
(fail-closed, CWE-284).

A caller's accessible organizations SHALL be derived from CyberdyneAuth's
dedicated `orgs` authorization claim when present. The claim lists the caller's
active organization memberships as `{id, short_name, github_login}`; the system
SHALL restrict the caller to the set of non-null `github_login` values (the key a
repository owner is matched against), case-insensitive. A **present** `orgs` claim
is authoritative: an empty set (or a set whose organizations have no
`github_login`) SHALL grant **no** organizations. A caller who is `is_admin` SHALL
be unrestricted regardless of the claim (policy).

When the `orgs` claim is **absent** — a legacy pre-`orgs` token, a service token,
or a Mnemosyne API key whose organization scope is encoded via plan-qualified
entitlements — the system SHALL fall back to the entitlement derivation: a caller
who holds the bare product entitlement or is admitted by service audience SHALL be
unrestricted; a caller whose only grant is one or more plan-qualified entitlements
(`product_key:<org>`) SHALL be restricted to exactly those organizations
(case-insensitive). The system SHALL NOT treat an absent claim as an empty
(deny-all) set.

The system SHALL set this boundary as soon as a caller's identity is proven — on
the base authenticated dependency, not only the entitled dependency — so no
authenticated request path is left at the unset default or an unrestricted view
(FINDING-025).

Every read of repository or organization data SHALL be limited to the boundary: a
repository outside scope SHALL be treated as not found, and organization-scoped,
cross-repository, and portfolio results SHALL exclude out-of-scope organizations.
An **unset** boundary SHALL expose no organizations.

Entrypoints that run without a per-caller identity but legitimately span every
organization — background worker jobs (repository sync, connection deletion,
scheduled discovery/sync) and signature-authenticated webhook processing — SHALL
explicitly grant the unrestricted state at entry. They SHALL NOT rely on the
default being unrestricted.

#### Scenario: Orgs claim scopes to its GitHub logins
- **WHEN** a caller whose `orgs` claim contains `{github_login: "CyberdyneCorp"}` lists repositories
- **THEN** only `cyberdynecorp` repositories SHALL be returned (case-insensitive match)

#### Scenario: Empty orgs claim denies every organization
- **WHEN** a non-admin caller presents an `orgs` claim that is empty (or whose orgs have no `github_login`)
- **THEN** every organization SHALL be treated as inaccessible

#### Scenario: Orgs claim overrides a billing-plan qualifier
- **WHEN** a caller holds entitlement `mnemosyne:premium` (a billing plan) and an `orgs` claim authorizing `acme`
- **THEN** the caller SHALL be scoped to `acme` and `premium` SHALL NOT be treated as an organization

#### Scenario: Absent orgs claim falls back to entitlements
- **WHEN** a caller presents a token with no `orgs` claim and entitlement `mnemosyne:CyberdyneCorp`
- **THEN** the caller SHALL be restricted to `cyberdynecorp` (legacy derivation)

#### Scenario: Unset boundary denies every organization
- **WHEN** repository or organization data is read with no organization boundary established
- **THEN** every organization SHALL be treated as inaccessible (out-of-scope repositories not found; rollups empty)

#### Scenario: Out-of-scope repository is not found
- **WHEN** an org-scoped caller requests a repository in a different organization by id
- **THEN** the response SHALL be 404 (REST) or a not-found error (MCP)
