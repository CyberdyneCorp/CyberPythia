# webhooks — receiver, idempotency, and event dispatch

## ADDED Requirements

### Requirement: Signature-validated webhook receiver
The system SHALL expose `POST /api/v1/webhooks/github` accepting GitHub webhook deliveries. The endpoint SHALL validate the `X-Hub-Signature-256` HMAC-SHA256 of the raw request body against the webhook secret of the matching installation. A delivery with a missing or invalid signature SHALL be rejected with 401 and SHALL NOT be processed. The endpoint SHALL NOT require a CyberdyneAuth bearer token.

#### Scenario: Valid signature accepted
- **WHEN** a delivery arrives whose `X-Hub-Signature-256` matches the HMAC of its body under the installation webhook secret
- **THEN** the delivery SHALL be accepted and dispatched to the appropriate handler

#### Scenario: Invalid signature rejected
- **WHEN** a delivery's signature does not match (or is absent)
- **THEN** the system SHALL respond 401 and SHALL NOT process the payload

#### Scenario: Constant-time comparison
- **WHEN** a signature is compared
- **THEN** the comparison SHALL be constant-time to avoid timing leaks

### Requirement: Delivery idempotency and audit
The system SHALL record each accepted delivery keyed by `X-GitHub-Delivery` (id, event, action, repository, outcome, timestamp). A delivery whose id has already been recorded SHALL be acknowledged with success without reprocessing.

#### Scenario: Redelivered event
- **WHEN** GitHub redelivers a webhook with an id already processed
- **THEN** the system SHALL respond success without producing duplicate sync work

#### Scenario: Delivery is audited
- **WHEN** a delivery is processed
- **THEN** an audit/delivery record SHALL be persisted with its event, action, target repository, and outcome

### Requirement: Event dispatch to incremental sync
The system SHALL dispatch validated events to incremental handlers:

```text
push                          -> enqueue a mode-appropriate sync for the repository
issues, issue_comment         -> upsert the single affected issue, then recompute metrics
pull_request, pull_request_review, pull_request_review_comment
                              -> upsert the single affected PR, then recompute metrics
repository                    -> update or remove repository metadata
installation, installation_repositories
                              -> add/remove repositories for the installation
```

Events for repositories that are not enabled for indexing SHALL be acknowledged and ignored. Unknown event types SHALL be acknowledged and ignored.

#### Scenario: Push triggers a sync
- **WHEN** a `push` event arrives for an enabled repository
- **THEN** a sync job for that repository SHALL be enqueued (subject to the per-repository sync lock)

#### Scenario: Issue event upserts one issue
- **WHEN** an `issues` event opens or edits an issue on an enabled repository
- **THEN** only that issue SHALL be fetched and upserted, and the repository's issue metrics SHALL be recomputed

#### Scenario: Event for a non-indexed repository
- **WHEN** an event arrives for a repository not enabled for indexing
- **THEN** the delivery SHALL be acknowledged and no sync work SHALL be produced

#### Scenario: Repository deleted
- **WHEN** a `repository` deleted event arrives
- **THEN** the repository SHALL be removed from indexing and no further syncs SHALL run for it
