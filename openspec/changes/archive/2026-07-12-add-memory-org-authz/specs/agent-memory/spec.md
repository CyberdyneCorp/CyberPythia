# agent-memory Specification

## ADDED Requirements

### Requirement: Memory access is scoped to the caller's organizations

Every recall, remember, and forget operation on a memory SHALL be limited to the
caller's accessible organizations, using the same per-organization boundary as
repository data. A caller who is unrestricted (admin, bare product entitlement,
service audience, or the background worker) SHALL reach any organization; a
caller restricted to a set of organizations SHALL reach only those
(case-insensitive).

Recalling or remembering a memory for an organization outside the caller's scope
SHALL be treated as not found (404 REST / not-found error MCP), and nothing SHALL
be written. Forgetting SHALL never delete by bare id: the system SHALL resolve
the memory's owner — the owning repository's organization for a repository-scoped
memory, or the `organization` field for an organization-scoped memory — and SHALL
treat a memory whose owner is outside the caller's scope (or that does not exist)
as not found, deleting nothing.

#### Scenario: Org-scoped caller cannot recall another organization's memories
- **WHEN** a caller scoped to `acme` recalls memories for organization `victim-org`
- **THEN** the response SHALL be not found and no `victim-org` memories SHALL be returned

#### Scenario: Org-scoped caller cannot write into another organization
- **WHEN** a caller scoped to `acme` records a memory for organization `victim-org`
- **THEN** the response SHALL be not found and nothing SHALL be persisted for `victim-org`

#### Scenario: Org-scoped caller cannot forget another organization's memory
- **WHEN** a caller scoped to `acme` deletes, by id, a memory owned by `victim-org`
  (organization-scoped or owned by a `victim-org` repository)
- **THEN** the response SHALL be not found and the memory SHALL remain

#### Scenario: Same-org and unrestricted callers retain full access
- **WHEN** a caller scoped to `acme` (or an unrestricted caller) recalls, records,
  or forgets a memory in an organization it may access
- **THEN** the operation SHALL succeed as before
