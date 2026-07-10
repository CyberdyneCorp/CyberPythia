# web-ui Specification

## ADDED Requirements

### Requirement: Safe connection deletion

The connections view SHALL guard connection deletion: it SHALL state how many
repositories and their indexed data will be destroyed, SHALL require the operator
to type the connection's owner to arm the Delete action, and SHALL surface
deletion failures instead of silently swallowing them.

#### Scenario: Typed confirmation required
- **WHEN** an operator initiates deletion of a connection
- **THEN** the Delete action SHALL remain disabled until the operator types the connection's owner, and the affected repository count SHALL be shown

#### Scenario: Failure is surfaced
- **WHEN** a deletion request fails
- **THEN** the view SHALL display the error
