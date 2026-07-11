# agent-memory Specification

## ADDED Requirements

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
an entitled caller delete a memory by id.

#### Scenario: Recall filtered memories
- **WHEN** a caller recalls a repository's memories with a query and/or kind
- **THEN** only matching memories SHALL be returned, newest first

#### Scenario: Forget a memory
- **WHEN** a caller deletes a memory by id
- **THEN** it SHALL be removed and absent from subsequent recalls
