# rest-api — GitHub App and webhook endpoints

## ADDED Requirements

### Requirement: GitHub App and webhook REST endpoints
The REST API SHALL add:

```text
POST   /api/v1/github/app/connect                              (admin)
GET    /api/v1/github/app/installations/{connection_id}/repos  (admin)
POST   /api/v1/webhooks/github                                 (public, signature-gated)
GET    /api/v1/admin/webhook-deliveries                        (admin)
```

The admin endpoints SHALL enforce bearer validation and admin authorization. The webhook endpoint SHALL be exempt from bearer auth and instead gated by HMAC signature validation, and SHALL always respond quickly (enqueue work rather than process synchronously where processing is non-trivial). All SHALL use the consistent error model, except the webhook endpoint which returns GitHub-friendly 2xx/401 responses.

#### Scenario: App connect documented and secured
- **WHEN** the OpenAPI document is fetched
- **THEN** the four endpoints SHALL be present, the admin ones declaring bearer security and the webhook one declaring none

#### Scenario: Webhook responds promptly
- **WHEN** a valid delivery arrives
- **THEN** the endpoint SHALL acknowledge with a 2xx after enqueuing/handling, without blocking on a full sync

#### Scenario: Delivery log
- **WHEN** an admin requests `/admin/webhook-deliveries`
- **THEN** recent deliveries SHALL be returned with event, action, repository, outcome, and timestamp
