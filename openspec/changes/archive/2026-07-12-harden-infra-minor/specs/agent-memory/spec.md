# agent-memory Specification

## MODIFIED Requirements

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
