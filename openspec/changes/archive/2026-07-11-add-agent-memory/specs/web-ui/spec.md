# web-ui Specification

## ADDED Requirements

### Requirement: Memory tab on the repository detail page

The repository detail page SHALL provide a Memory tab that lists the repository's
memories (newest first) and lets the operator add a memory (content + kind) and
delete one.

#### Scenario: Add and see a memory
- **WHEN** an operator adds a memory on the Memory tab
- **THEN** it SHALL appear in the list without a full page reload

#### Scenario: Delete a memory
- **WHEN** an operator deletes a memory
- **THEN** it SHALL be removed from the list
