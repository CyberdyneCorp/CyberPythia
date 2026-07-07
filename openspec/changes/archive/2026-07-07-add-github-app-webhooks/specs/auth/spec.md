# auth — webhook endpoint exemption

## ADDED Requirements

### Requirement: Webhook endpoint is signature-gated, not bearer-gated
The webhook receiver (`POST /api/v1/webhooks/github`) SHALL be exempt from the CyberdyneAuth bearer-token requirement, since GitHub cannot present a CyberdyneAuth token. It SHALL instead be gated by HMAC-SHA256 signature validation against the installation webhook secret. This is the only non-health endpoint permitted to bypass bearer validation, and it SHALL reject unsigned or mis-signed requests.

#### Scenario: Webhook without a bearer token
- **WHEN** GitHub calls the webhook endpoint with a valid signature but no `Authorization` header
- **THEN** the request SHALL be accepted (signature is the gate)

#### Scenario: Webhook with an invalid signature
- **WHEN** a request to the webhook endpoint has no valid signature
- **THEN** it SHALL be rejected with 401 regardless of any bearer token
