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

### Requirement: Intelligence excludes un-indexed repositories
Engineering-intelligence and delivery-intelligence SHALL only consider repositories that are
currently indexed (enabled). Portfolio and scorecard aggregations SHALL exclude disabled
repositories, and per-repository intelligence (health, delivery, flow, backlog, forecast,
work-mix, quality, milestones, team-load, maintenance-risk, review-bottlenecks, onboarding) SHALL
treat a disabled repository as not indexed and return a not-found/not-indexed result rather than
its stale persisted metrics.

#### Scenario: Disabled repository is not in the portfolio
- **GIVEN** a repository that has been disabled
- **WHEN** the portfolio overview or delivery scorecard is requested
- **THEN** that repository SHALL NOT be included

#### Scenario: Per-repo intelligence on a disabled repository is rejected
- **GIVEN** a repository that has persisted metrics but is now disabled
- **WHEN** its per-repository intelligence is requested
- **THEN** the system SHALL respond that the repository is not indexed rather than returning its data

#### Scenario: Re-indexing restores it
- **GIVEN** a repository re-enabled for indexing
- **WHEN** intelligence is requested
- **THEN** it SHALL be considered again

### Requirement: Organization-scoped rollups and capability overviews

The intelligence layer SHALL support scoping the portfolio overview and delivery
scorecard to a single organization, and SHALL compute an organization rollup
(scored/total, average and median health, grade distribution, at-risk milestone
total, throughput directions) from the scoped portfolio and scorecard. It SHALL also
compute capability overviews for a repository and for an organization, derived
(without an LLM) from indexed OpenSpec spec areas, documentation topics, and metrics
(including a bug count from bug-labelled issues).

#### Scenario: Organization rollup aggregation
- **WHEN** a rollup is requested for an organization
- **THEN** it SHALL aggregate only that organization's indexed repositories, leaving health absent when no repository has been scored

#### Scenario: Capability overview
- **WHEN** a capability overview is requested for a repository
- **THEN** it SHALL list the repository's OpenSpec spec areas, documentation topics, bug count, and issue/PR counts

#### Scenario: Absent data stays absent
- **WHEN** an organization has no scored repositories
- **THEN** the rollup's average and median health SHALL be absent rather than zero

### Requirement: Project readiness classification

The intelligence layer SHALL classify a repository into one of three readiness gates
— MVP, READY, DONE — from observable signals only, and SHALL report each gate check as
`met`, `missing`, or `unknown`. A check is `unknown` when its signal is not captured by
the repository's indexing mode (e.g. CI/tests when no file tree is indexed) and SHALL
NOT count toward a gate. READY SHALL require CI, tests, a documented design (OpenSpec or
an ADR document), at least one closed issue and one merged pull request, a README, and a
guide document. DONE SHALL require READY plus a dependency manifest, monitoring
(Dependabot or a security-scanning workflow), a SECURITY document, a low open-bug ratio,
and at least one published GitHub Release. The layer SHALL also produce an
organization-level distribution (counts per gate) with each repository's gate and what
it is missing to reach READY.

#### Scenario: Repository meeting all READY checks
- **WHEN** a repository has CI, tests, OpenSpec/ADRs, a closed issue, a merged PR, a README, and a guide doc
- **THEN** it SHALL be classified READY with no missing READY checks

#### Scenario: Unknown signal cannot satisfy a gate
- **WHEN** a repository's indexing mode captures no file tree, so CI/tests are unknown
- **THEN** those checks SHALL be reported `unknown` and the repository SHALL NOT be classified READY on them

#### Scenario: DONE requires observable hardening and a release
- **WHEN** a READY repository additionally has a dependency manifest, monitoring, a SECURITY doc, a low open-bug ratio, and at least one published release
- **THEN** it SHALL be classified DONE

#### Scenario: A release is required for DONE
- **WHEN** a repository meets every other DONE check but has no published release
- **THEN** the `releases` check SHALL be `missing` and the repository SHALL NOT be classified DONE

#### Scenario: Organization distribution
- **WHEN** an organization readiness rollup is requested
- **THEN** it SHALL return per-gate counts and each repository's gate plus its missing-for-READY checks

### Requirement: Readiness history and regression detection

The intelligence layer SHALL record each repository's readiness gate at most once
per UTC day, building a per-repository time series. It SHALL expose a
repository's readiness trend, and an organization-level list of **regressions** —
repositories whose most recent recorded gate is lower than their previous
recorded gate (ranking MVP < READY < DONE) — including the previous gate, the
current gate, and the date the change was recorded.

Recording SHALL happen as part of the daily scheduled run, after syncing.
Historical gates SHALL NOT be back-filled; the series accrues from first record.

#### Scenario: Daily gate recorded
- **WHEN** the scheduled readiness recording runs for a repository
- **THEN** a snapshot with that day's gate SHALL be stored, and a second run on the same day SHALL update rather than duplicate it

#### Scenario: Regression surfaced
- **WHEN** a repository's latest recorded gate is lower than its previous recorded gate
- **THEN** the organization regressions view SHALL include it with its previous gate, current gate, and the date

#### Scenario: Stable or improving repositories are not regressions
- **WHEN** a repository's latest gate is equal to or higher than its previous gate
- **THEN** it SHALL NOT appear in the regressions view

