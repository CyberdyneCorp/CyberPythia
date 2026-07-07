# rest-api — sync observability admin endpoints

## ADDED Requirements

### Requirement: Scheduled-run and sync-job admin endpoints
The REST API SHALL expose admin-only endpoints to observe sync activity:

- `GET /api/v1/admin/sync-runs` — recent scheduled-run summaries (timestamps, trigger, discovery
  and sync counters), newest first.
- `GET /api/v1/admin/sync-jobs` — recent per-repository sync jobs with the repository name, status,
  trigger, start/finish times, and any failed-step error messages.

Both endpoints SHALL require admin authorization and SHALL reject non-admin callers.

#### Scenario: Admin lists recent scheduled runs
- **GIVEN** an admin caller and at least one recorded scheduled run
- **WHEN** `GET /api/v1/admin/sync-runs` is called
- **THEN** the response SHALL list the run summaries newest first

#### Scenario: Admin sees a failed sync and its reason
- **GIVEN** a sync job that failed (for example, rate-limited)
- **WHEN** `GET /api/v1/admin/sync-jobs` is called by an admin
- **THEN** the response SHALL include that job with its status and the failed-step error text

#### Scenario: Non-admin rejected
- **GIVEN** a caller without admin authorization
- **WHEN** either endpoint is called
- **THEN** the API SHALL reject the request
