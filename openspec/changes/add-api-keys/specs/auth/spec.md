# auth Specification

## ADDED Requirements

### Requirement: Mnemosyne API keys as an alternative bearer credential

The system SHALL accept a Mnemosyne-issued API key as an alternative bearer
credential on both REST and MCP requests, in addition to CyberdyneAuth tokens.
An API key SHALL be a string with the reserved prefix `mnem_` followed by a
high-entropy secret. The system SHALL store only a SHA-256 hash of the key and
SHALL NOT persist the plaintext. A presented bearer that begins with `mnem_`
SHALL be validated against stored keys; any other bearer SHALL be validated by
the existing CyberdyneAuth path unchanged.

A valid API key SHALL resolve to a caller identity that carries the required
`mnemosyne` entitlement (read/query access). An API-key caller SHALL NOT be
treated as an administrator and SHALL be denied admin-only operations.

#### Scenario: Valid API key grants query access
- **WHEN** a request carries a bearer token beginning with `mnem_` whose SHA-256 hash matches a stored key that is not revoked and not expired
- **THEN** the system SHALL resolve a caller with the `mnemosyne` entitlement and process the request as an entitled (non-admin) caller

#### Scenario: Unknown API key
- **WHEN** a request carries an `mnem_` bearer whose hash matches no stored key
- **THEN** the system SHALL respond 401 (REST) or raise an unauthenticated tool error (MCP)

#### Scenario: Expired API key
- **WHEN** a request carries an `mnem_` bearer whose stored key has an `expires_at` in the past
- **THEN** the system SHALL reject it as unauthenticated

#### Scenario: Revoked API key
- **WHEN** a request carries an `mnem_` bearer whose stored key has been revoked
- **THEN** the system SHALL reject it as unauthenticated

#### Scenario: Non-API-key bearer is unaffected
- **WHEN** a request carries a bearer token that does not begin with `mnem_`
- **THEN** the system SHALL validate it via CyberdyneAuth exactly as before

#### Scenario: API key cannot perform admin operations
- **WHEN** a caller authenticated by an API key invokes an admin-only endpoint
- **THEN** the system SHALL respond 403 (administrator privileges required)
