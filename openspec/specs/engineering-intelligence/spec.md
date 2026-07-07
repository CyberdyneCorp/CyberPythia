# engineering-intelligence Specification

## Purpose
TBD - created by archiving change add-engineering-intelligence. Update Purpose after archive.
## Requirements
### Requirement: Repository signal detection
The system SHALL derive presence signals from a repository's captured file tree: `has_ci`, `has_tests`, `has_dependency_manifest`, `has_contributing`, and `has_license`. When the repository's indexing mode does not capture a file tree, each signal SHALL be reported as **unknown** (not `false`), and unknown signals SHALL NOT count against any score.

#### Scenario: CI and tests detected from the tree
- **GIVEN** a repository indexed in a mode that captures the file tree
- **AND** the tree contains `.github/workflows/ci.yml` and a `tests/` directory
- **WHEN** signals are detected
- **THEN** `has_ci` SHALL be `true` and `has_tests` SHALL be `true`

#### Scenario: Signals unknown when no tree is captured
- **GIVEN** a repository indexed in `docs_only` or `project_intelligence` mode
- **WHEN** signals are detected
- **THEN** every file-tree signal SHALL be reported as `unknown`

### Requirement: Repository health score
The system SHALL compute a repository health score from the repository's persisted metrics and signals, producing component sub-scores (documentation, delivery, maintenance, testing/CI, activity) each in the range 0–100 or `null` when its inputs are absent, a weighted **overall score in the range 0–100**, and a **letter grade** (A ≥ 90, B ≥ 75, C ≥ 60, D ≥ 40, otherwise F). A component whose inputs are absent or unknown SHALL be excluded from the weighted overall, and the remaining component weights SHALL be renormalised. The result SHALL include, for each component, the inputs and weight used, and a ranked list of findings explaining the score.

#### Scenario: Fully-populated repository scored
- **GIVEN** a repository with README, docs, merged PRs, and captured CI/tests
- **WHEN** its health is computed
- **THEN** each component SHALL have a numeric sub-score, the overall SHALL be the renormalised weighted mean, and a grade SHALL be assigned

#### Scenario: Missing component is excluded, not zeroed
- **GIVEN** a repository whose indexing mode does not capture a file tree
- **WHEN** its health is computed
- **THEN** the testing/CI component SHALL be `null`, SHALL NOT contribute to the overall, and the remaining weights SHALL renormalise to sum to 1

#### Scenario: Score is explainable
- **WHEN** a repository health score is computed
- **THEN** the result SHALL list the findings (severity, message, triggering metric) that account for lost points

#### Scenario: Never-synced repository
- **GIVEN** a repository that has not been synced
- **WHEN** its health is requested
- **THEN** the system SHALL report insufficient data rather than a fabricated score

### Requirement: Delivery metrics
The system SHALL expose per-repository delivery analytics — cycle/lead time, PR size distribution, throughput (merged PRs and closed issues over the captured window), and merge rate — computed from persisted PR and issue metrics, with any metric over an empty population reported as `null`.

#### Scenario: Delivery metrics for an active repository
- **GIVEN** a repository with merged PRs and closed issues
- **WHEN** delivery metrics are requested
- **THEN** the system SHALL return median merge time, PR size distribution, and throughput

#### Scenario: No merged PRs
- **GIVEN** a repository with no merged PRs
- **WHEN** delivery metrics are requested
- **THEN** merge-time metrics SHALL be `null` and labelled as insufficient data

### Requirement: Backlog metrics
The system SHALL expose per-repository backlog analytics: open-issue count, stale-issue count and list, open/closed ratio, and oldest-open-issue age.

#### Scenario: Backlog with stale issues
- **GIVEN** a repository with open issues older than the stale threshold
- **WHEN** backlog metrics are requested
- **THEN** the stale issues SHALL be listed newest-debt-first with their ages

### Requirement: Review bottleneck detection
The system SHALL identify review bottlenecks for a repository: open PRs with slow or absent first review, and reviewer-load concentration across the captured reviewer distribution.

#### Scenario: Slow-review PRs surfaced
- **GIVEN** a repository with open PRs that have no review after the stale threshold
- **WHEN** review bottlenecks are requested
- **THEN** those PRs SHALL be listed and the reviewer-load concentration reported

### Requirement: Maintenance risk assessment
The system SHALL compute a maintenance-risk assessment per repository as a risk level with explicit reasons, drawn from a fixed signal set: archived-but-enabled, missing CI, missing tests, stale-issue/PR accumulation, stale last-sync, and high open-issue backlog. Signals that are unknown SHALL NOT raise the risk level.

#### Scenario: At-risk repository
- **GIVEN** a repository that is archived yet still enabled and has many stale issues
- **WHEN** maintenance risk is assessed
- **THEN** the system SHALL report an elevated risk level listing those reasons

#### Scenario: Unknown signal does not inflate risk
- **GIVEN** a repository whose mode does not capture a file tree (CI/tests unknown)
- **WHEN** maintenance risk is assessed
- **THEN** the unknown CI/tests signals SHALL NOT contribute to the risk level

### Requirement: Portfolio intelligence
The system SHALL aggregate all enabled repositories into a portfolio overview: a health-ranked leaderboard, the most-active repositories (by recent issue/PR/merge volume), abandoned repositories (no activity within a configured window), and bug-heavy repositories (by "bug"/"defect" label volume). Repositories lacking metrics SHALL be included with an insufficient-data marker rather than omitted silently.

#### Scenario: Portfolio overview across repositories
- **GIVEN** multiple enabled repositories with metrics
- **WHEN** the portfolio overview is requested
- **THEN** the system SHALL return the leaderboard, most-active, abandoned, and bug-heavy groupings

#### Scenario: Repository without metrics is marked, not dropped
- **GIVEN** an enabled repository that has never been synced
- **WHEN** the portfolio overview is requested
- **THEN** that repository SHALL appear with an insufficient-data marker

### Requirement: Repository comparison
The system SHALL compare a chosen set of repositories by aligning their health scores and key delivery/backlog metrics into a single comparison view.

#### Scenario: Compare two repositories
- **GIVEN** two synced repositories
- **WHEN** they are compared
- **THEN** the system SHALL return their health grades and aligned metrics side by side

### Requirement: Onboarding summary
The system SHALL generate a newcomer-facing onboarding summary for a repository, composing its health assessment, documentation/OpenSpec presence, and repository-structure explanation.

#### Scenario: Onboarding summary for a synced repository
- **GIVEN** a synced repository with documentation
- **WHEN** an onboarding summary is generated
- **THEN** the system SHALL return a brief combining health, docs presence, and structure

