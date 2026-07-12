# auth Specification

## ADDED Requirements

### Requirement: Per-organization access scoping

A caller's accessible organizations SHALL be derived from CyberdyneAuth
entitlements: a caller who is `is_admin`, holds the bare product entitlement, or
is admitted by service audience SHALL have access to all indexed organizations;
a caller whose only grant is one or more plan-qualified entitlements
(`product_key:<org>`) SHALL be restricted to exactly those organizations
(case-insensitive). Every read of repository or organization data SHALL be
limited to the caller's accessible organizations: a repository outside scope
SHALL be treated as not found, and organization-scoped, cross-repository, and
portfolio results SHALL exclude out-of-scope organizations. Background sync
(no caller) SHALL be unrestricted.

#### Scenario: Org-scoped caller sees only its organization
- **WHEN** a caller whose entitlement is `mnemosyne:CyberdyneCorp` lists repositories
- **THEN** only `CyberdyneCorp` repositories SHALL be returned

#### Scenario: Out-of-scope repository is not found
- **WHEN** an org-scoped caller requests a repository in a different organization by id
- **THEN** the response SHALL be 404 (REST) or a not-found error (MCP)

#### Scenario: Unscoped caller sees everything
- **WHEN** a caller holds the bare `mnemosyne` entitlement or is `is_admin`
- **THEN** repositories across all indexed organizations SHALL be accessible
