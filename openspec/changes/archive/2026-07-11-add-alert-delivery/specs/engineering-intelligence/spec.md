# engineering-intelligence Specification

## ADDED Requirements

### Requirement: Organization attention digest and delivery

The intelligence layer SHALL assemble a per-organization **digest** of
attention-worthy signals — readiness regressions, the oldest stale open issues
and pull requests, and at-risk milestones — with a human-readable summary. The
digest SHALL be available on demand, and when an outbound alert webhook is
configured the daily scheduled run SHALL deliver each enabled organization's
non-empty digest to it. Delivery SHALL be best-effort and SHALL NOT fail the
scheduled run.

#### Scenario: Digest assembled on demand
- **WHEN** a digest is requested for an organization
- **THEN** it SHALL contain that org's readiness regressions, stale issues/PRs, at-risk milestones, and a summary line

#### Scenario: Daily delivery when configured
- **WHEN** the daily run completes and an alert webhook is configured
- **THEN** each enabled organization's non-empty digest SHALL be POSTed to the webhook

#### Scenario: Delivery failure is contained
- **WHEN** the alert webhook is unreachable
- **THEN** the scheduled run SHALL still complete successfully
