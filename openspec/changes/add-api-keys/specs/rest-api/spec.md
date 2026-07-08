# rest-api Specification

## ADDED Requirements

### Requirement: API key management endpoints

The system SHALL expose admin-only REST endpoints to create, list, and revoke
Mnemosyne API keys under `/api/v1/api-keys`. Creation SHALL accept a human label
and an optional expiry (a number of days, or none for a non-expiring key) and
SHALL return the plaintext key exactly once in the creation response. Listing
SHALL return key metadata only (id, label, display prefix, creator, timestamps,
expiry, revoked state) and SHALL NOT return the plaintext or the hash. Every
creation and revocation SHALL be recorded as an audit event.

#### Scenario: Create a key
- **WHEN** an admin `POST`s `/api/v1/api-keys` with a label and optional `expires_in_days`
- **THEN** the system SHALL create the key, record an audit event, and respond 201 with the plaintext key, its id, display prefix, and computed `expires_at`

#### Scenario: Plaintext returned only once
- **WHEN** an admin lists keys via `GET /api/v1/api-keys`
- **THEN** the response SHALL contain metadata only and SHALL NOT include the plaintext key or its hash

#### Scenario: Revoke a key
- **WHEN** an admin `DELETE`s `/api/v1/api-keys/{id}`
- **THEN** the system SHALL mark the key revoked, record an audit event, and the key SHALL no longer authenticate

#### Scenario: Non-admin denied
- **WHEN** a non-admin caller invokes any `/api/v1/api-keys` management endpoint
- **THEN** the system SHALL respond 403
