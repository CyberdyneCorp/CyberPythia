# web-ui Specification

## ADDED Requirements

### Requirement: Intelligence regressions, vulnerabilities, and capabilities panels

When an organization is selected, the Intelligence page SHALL show a readiness
**regressions** panel (repositories whose gate dropped, with from/to gate and
date), a **vulnerabilities** panel (repositories with open critical/high
Dependabot alerts plus org totals), and an organization **capabilities** card
(capability areas, repository count, total open bugs). The readiness panel SHALL
also show, for READY repositories, what they are missing to reach DONE.

#### Scenario: Regressions shown for an organization
- **WHEN** a user selects an organization and readiness regressions exist
- **THEN** the regressions panel SHALL list each repository with its previous and current gate and the date

#### Scenario: Vulnerabilities shown for an organization
- **WHEN** a user selects an organization
- **THEN** the vulnerabilities panel SHALL show repositories with open critical/high alert counts and the org totals

#### Scenario: Capabilities shown for an organization
- **WHEN** a user selects an organization
- **THEN** the capabilities card SHALL show the union of capability areas, repository count, and total open bugs
