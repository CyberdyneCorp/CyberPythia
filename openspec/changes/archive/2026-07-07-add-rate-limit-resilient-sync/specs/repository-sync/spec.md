# repository-sync — rate-limit-resilient scheduled sync

## ADDED Requirements

### Requirement: Staggered scheduled fan-out
When the scheduled job enqueues syncs for the enabled repositories, it SHALL spread the enqueues
over time by an increasing per-repository delay, rather than enqueuing them all at once, to smooth
the request rate against GitHub. The stagger interval SHALL be configurable.

#### Scenario: Enqueues are spread, not bursted
- **WHEN** the scheduled sync enqueues syncs for many enabled repositories
- **THEN** each successive repository's sync SHALL be deferred by a progressively larger delay

#### Scenario: All enabled repositories are still enqueued
- **WHEN** the scheduled sync runs with staggering enabled
- **THEN** every enabled repository SHALL still be enqueued (staggering delays, it does not drop any)

### Requirement: Bounded rate-limit wait with fail-fast
When a GitHub request is rate-limited, the system SHALL determine the wait until the limit resets
from `X-RateLimit-Reset` or `Retry-After`. If the wait is within a configurable maximum, the system
SHALL wait and retry; if the wait exceeds that maximum, the system SHALL fail the request with a
distinct rate-limit error rather than blocking, so the worker slot is freed and the affected
repository is retried on the next scheduled run.

#### Scenario: Short limit is absorbed
- **GIVEN** a rate-limited response whose reset is within the maximum wait
- **WHEN** the request is made
- **THEN** the system SHALL wait until reset and retry the request

#### Scenario: Long limit fails fast
- **GIVEN** a rate-limited response whose reset is beyond the maximum wait
- **WHEN** the request is made
- **THEN** the system SHALL raise a rate-limit error immediately without blocking for the full reset

#### Scenario: Secondary limit honours Retry-After
- **GIVEN** a rate-limited response carrying a `Retry-After` header within the maximum wait
- **WHEN** the request is made
- **THEN** the system SHALL wait the indicated seconds and retry
