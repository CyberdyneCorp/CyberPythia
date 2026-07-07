# Proposal: add-engineering-intelligence

## Why

Mnemosyne already captures the raw material of engineering intelligence — per-repository issue and PR metrics, documentation/OpenSpec presence, file trees, and stale-issue/PR lists — and recomputes them on every sync and webhook. But that data is only exposed one repository at a time, as flat numbers. There is no **health score** that tells a PM "which repos are at risk", no **portfolio view** that tells the business "which repos are active vs. abandoned", and no **bottleneck detection** that tells a lead "where reviews are stuck". Phase 5 turns the captured data into decisions.

Phase 5 is deliberately a **read/compute/aggregation layer**: it derives scores and rollups from the `repository_metrics` rows and file trees that already exist and stay fresh via incremental sync. It captures no new GitHub data and — apart from an optional health-snapshot for trends — adds no new heavy persistence. That keeps it low-risk and fast to ship on top of the shipped core, Phase 3, and Phase 4.

## What Changes

- **Repository signals** (`RepositorySignalsService`, pure): derive presence signals from the captured file tree — `has_ci` (`.github/workflows/*`, `.gitlab-ci.yml`, `.circleci/`, `azure-pipelines.yml`), `has_tests` (test dirs / `*_test.*` / `test_*.*` / `*.spec.*` patterns), `has_dependency_manifest`, `has_contributing`, `has_license`. When a repository's indexing mode does not capture a file tree, each signal is **`unknown`, not `false`** (absent-not-zero discipline).
- **Repository health score** (`RepositoryHealthService`, pure): combine documentation/OpenSpec presence, delivery metrics, maintenance signals, and activity into component sub-scores (each 0–100 or `null` when the inputs are absent), a weighted **overall score (0–100)** and **letter grade (A–F)**, plus a ranked list of concrete **findings** (e.g. "No CI configured", "12 issues stale > 30d", "Median PR merge time 9d"). Scoring is transparent: every component reports its inputs and weight.
- **Delivery, backlog, review-bottleneck, and maintenance-risk analytics** (application services over the persisted metrics): cycle/lead time, PR size distribution, backlog growth and stale accumulation, reviewer load concentration + slow-first-review PRs, and a maintenance-risk roll-up (archived-but-enabled, no CI/tests, stale-heavy, no recent sync).
- **Portfolio / cross-repo intelligence**: aggregate all indexed repositories into an org overview — most active, abandoned (no recent activity), bug-heavy areas, and a health-ranked leaderboard — and a `compare_repositories` view. `generate_onboarding_summary` composes a repo's health + docs + structure into a newcomer-facing brief.
- **MCP tools** (new): `mnemosyne_get_repository_health`, `mnemosyne_get_delivery_metrics`, `mnemosyne_get_backlog_metrics`, `mnemosyne_get_review_bottlenecks`, `mnemosyne_get_maintenance_risk`, `mnemosyne_get_portfolio_overview`, `mnemosyne_compare_repositories`, `mnemosyne_generate_onboarding_summary`.
- **REST endpoints** (new, under existing auth + entitlement): the per-repo analytics above plus `GET /api/v1/intelligence/portfolio` and `GET /api/v1/intelligence/repositories/{id}/health`.
- **Web UI**: an **Intelligence dashboard** (portfolio overview: health leaderboard, activity, risk) and a **health panel** on the repository detail page (score, grade, component breakdown, findings).

### Non-goals (future changes)

- **Historical trend lines / regression alerts.** Health is computed on-demand from current metrics. A `repository_health_snapshots` table + trend deltas is scoped as a follow-up (5.1); this change persists no time series.
- **Team/people analytics beyond what the captured `by_assignee`/`by_reviewer` maps already provide** (no org-chart, no cross-repo person identity resolution).
- **Configurable/tunable scoring weights via UI.** Weights are code-defined constants (documented); making them per-org-configurable is future work.
- **Dependency freshness / CVE scanning** (requires resolving and querying dependency versions — out of scope; `has_dependency_manifest` only detects presence).

## Capabilities

### New Capabilities

- `engineering-intelligence`: repository signal detection, health scoring, delivery/backlog/bottleneck/maintenance-risk analytics, and cross-repo portfolio aggregation.

### Modified Capabilities

None behaviorally changed (additive). Deltas add requirements to existing capabilities:

- `mcp-interface`: ADDED — eight engineering-intelligence tools.
- `rest-api`: ADDED — per-repo analytics + portfolio + health endpoints.
- `web-ui`: ADDED — intelligence dashboard + repository health panel.

## Impact

- **Data model**: none required (health + analytics computed on-demand from the existing `repository_metrics` rows + file tree). No migration in this change.
- **Code**: new domain (`RepositorySignalsService`, `RepositoryHealthService`, health/score value objects), application services for delivery/backlog/bottleneck/maintenance/portfolio analytics, MCP tool registrations, REST router, and Svelte dashboard + health panel (MVVM).
- **Dependencies**: none new (pure Python + existing stack).
- **Security**: read-only analytics behind the existing CyberdyneAuth bearer + `mnemosyne` entitlement; no new public surface. Analytics never expose data a caller could not already read via the existing per-repo tools.
- **Performance**: portfolio aggregation reads all `repository_metrics` rows (one row per repo, already summarized) — cheap; per-repo health is a pure computation over one repo's already-loaded metrics. Results are cache-friendly (keyed by repo + metrics `computed_at`).
- **Cost/latency**: no additional GitHub or embedding calls; scoring is CPU-only over persisted data.
