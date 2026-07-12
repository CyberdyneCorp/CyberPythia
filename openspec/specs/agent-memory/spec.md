# agent-memory Specification

## Purpose
TBD - created by archiving change add-agent-memory. Update Purpose after archive.
## Requirements
### Requirement: Memory store scoped to a repository or organization

The system SHALL let an entitled caller persist a **memory** — free-text
`content` with a `kind` (e.g. note, decision, gotcha, convention, todo) and the
caller's identity as author — scoped either to a repository or to an
organization. Memory is written only to Mnemosyne's own store, never to GitHub.
A memory SHALL record its creation time. Deleting a repository (or its
connection) SHALL cascade-delete its repository-scoped memories.

#### Scenario: Record a repository memory
- **WHEN** an entitled caller records a memory for a repository
- **THEN** it SHALL be stored with the content, kind, author, scope, and creation time

#### Scenario: Record an organization memory
- **WHEN** an entitled caller records a memory scoped to an organization
- **THEN** it SHALL be stored against that organization rather than a single repository

### Requirement: Recall and forget memories

The system SHALL return a scope's memories newest-first, optionally filtered by
`kind` and by a text `query` (substring/trigram match on content), and SHALL let
an entitled caller delete a memory by id. The `query` SHALL be matched literally:
`LIKE`/`ILIKE` metacharacters in the caller's input (`%`, `_`, `\`) SHALL be
escaped so they match the corresponding characters rather than acting as
wildcards, and the query length SHALL be bounded.

#### Scenario: Recall filtered memories
- **WHEN** a caller recalls a repository's memories with a query and/or kind
- **THEN** only matching memories SHALL be returned, newest first

#### Scenario: Query metacharacters match literally
- **WHEN** a caller recalls memories with a query containing `%` or `_`
- **THEN** only memories whose content contains those characters literally SHALL match, and the metacharacters SHALL NOT act as wildcards

#### Scenario: Forget a memory
- **WHEN** a caller deletes a memory by id
- **THEN** it SHALL be removed and absent from subsequent recalls

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

