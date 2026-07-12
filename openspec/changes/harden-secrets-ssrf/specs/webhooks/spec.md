# webhooks Specification

## MODIFIED Requirements

### Requirement: Signature-validated webhook receiver
The system SHALL expose `POST /api/v1/webhooks/github` accepting GitHub webhook deliveries. The endpoint SHALL validate the `X-Hub-Signature-256` HMAC-SHA256 of the raw request body against the webhook secret of the matching installation. A delivery with a missing or invalid signature SHALL be rejected with 401 and SHALL NOT be processed. A stored webhook secret that is empty or blank SHALL be treated as "no secret" — the delivery SHALL be rejected with 401 rather than verified under a known-empty HMAC key (CWE-347). The endpoint SHALL NOT require a CyberdyneAuth bearer token.

#### Scenario: Valid signature accepted
- **WHEN** a delivery arrives whose `X-Hub-Signature-256` matches the HMAC of its body under the installation webhook secret
- **THEN** the delivery SHALL be accepted and dispatched to the appropriate handler

#### Scenario: Invalid signature rejected
- **WHEN** a delivery's signature does not match (or is absent)
- **THEN** the system SHALL respond 401 and SHALL NOT process the payload

#### Scenario: Empty stored secret rejects the delivery
- **WHEN** a delivery arrives for an installation whose stored webhook secret is empty or blank
- **THEN** the system SHALL respond 401 and SHALL NOT verify the signature under the empty key

#### Scenario: Constant-time comparison
- **WHEN** a signature is compared
- **THEN** the comparison SHALL be constant-time to avoid timing leaks
