# web-ui Specification

## ADDED Requirements

### Requirement: Readiness on the Intelligence view

When an organization is selected, the Intelligence page SHALL show a readiness section:
the MVP/READY/DONE distribution and a per-repository list with each repository's gate
badge and, for repositories below READY, what they are missing.

#### Scenario: Readiness distribution for an organization
- **WHEN** a user selects an organization on the Intelligence page
- **THEN** the readiness distribution and per-repository gate badges SHALL be shown, with missing-for-READY checks for repositories below READY
