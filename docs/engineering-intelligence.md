# Engineering Intelligence (Phase 5)

Phase 5 turns the data Mnemosyne already captures — issue/PR metrics, docs/OpenSpec
presence, and the file tree — into decisions: a per-repository **health score**,
delivery/backlog/bottleneck/maintenance analytics, and a cross-repo **portfolio**
overview. It adds no new GitHub calls and no migration; everything is computed
on-demand from the `repository_metrics` rows that every sync and webhook keep fresh.

## The health score

A repository's health is a weighted mean of five components, each scored 0–100 or
reported as **not applicable** when its inputs are absent (never a fabricated 0). A
component that is not applicable drops out and the remaining weights renormalise, so
a docs-only repository is not penalised for CI it was never asked to capture.

| Component     | Weight | Inputs |
|---------------|--------|--------|
| documentation | 0.25   | README + docs presence, OpenSpec adoption |
| delivery      | 0.25   | merge rate, median PR merge time, median issue resolution time |
| maintenance   | 0.20   | stale open issues/PRs relative to open count |
| testing_ci    | 0.15   | `has_tests` + `has_ci` file-tree signals |
| activity      | 0.15   | recency of the last repository activity |

**Grades:** A ≥ 90, B ≥ 75, C ≥ 60, D ≥ 40, otherwise F.

The score is explainable: every component reports the inputs and weight it used, and
the result carries ranked **findings** (severity + message + the triggering metric)
that account for lost points — e.g. "No CI configured", "12 stale open items".

### Signals and indexing mode

File-tree signals (`has_ci`, `has_tests`, `has_dependency_manifest`,
`has_contributing`, `has_license`) are derived from captured paths. When the indexing
mode does **not** capture a file tree (`docs_only`, `project_intelligence`), each
signal is **unknown** — shown as *n/a*, excluded from the score, and never counted
against maintenance risk. Only `code_metadata` and richer modes yield tree signals.

## Analytics

- **Delivery** — cycle/lead time, PR size distribution, throughput, merge rate.
- **Backlog** — open/stale issues, open-to-closed ratio, oldest-open age.
- **Review bottlenecks** — slow/absent-review PRs and reviewer-load concentration
  (the top reviewer's share of all reviews; 1.0 = a single-reviewer bottleneck).
- **Maintenance risk** — a level (low/medium/high) with explicit reasons: archived
  but still enabled, no CI, no tests, stale accumulation, stale last-sync, high backlog.
- **Portfolio** — health leaderboard, most-active, abandoned, and bug-heavy repos across
  the org. Repositories without metrics appear with an insufficient-data marker rather
  than being dropped.

## Absent-not-zero

Every score, average, and rate is `null` (surfaced as "—"/"insufficient data") when
its population is empty, and the tools say *why* — not synced yet, mode doesn't capture
it, or no PRs merged. A repository with zero merged PRs reads as "no delivery data",
not "delivery score 0". This is what keeps the intelligence trustworthy.

## MCP tools

All require the same bearer + `mnemosyne` entitlement as the other tools and return
structured JSON (insufficient data is a structured result, not an error):

- `mnemosyne_get_repository_health`
- `mnemosyne_get_delivery_metrics`
- `mnemosyne_get_backlog_metrics`
- `mnemosyne_get_review_bottlenecks`
- `mnemosyne_get_maintenance_risk`
- `mnemosyne_get_portfolio_overview`
- `mnemosyne_compare_repositories`
- `mnemosyne_generate_onboarding_summary`

## REST endpoints

Under `/api/v1/intelligence`, all requiring the `mnemosyne` entitlement:

```
GET  /api/v1/intelligence/portfolio
GET  /api/v1/intelligence/repositories/{id}/health
GET  /api/v1/intelligence/repositories/{id}/delivery
GET  /api/v1/intelligence/repositories/{id}/backlog
GET  /api/v1/intelligence/repositories/{id}/review-bottlenecks
GET  /api/v1/intelligence/repositories/{id}/maintenance-risk
GET  /api/v1/intelligence/repositories/{id}/onboarding
POST /api/v1/intelligence/compare        # { "repository_ids": [...] }
```

## Web UI

- **Intelligence** dashboard (`/intelligence`): the portfolio health leaderboard plus
  most-active, abandoned, and bug-heavy groupings.
- **Health panel** on each repository detail page: overall score, grade, the component
  breakdown (with *n/a* for components the mode can't score), and findings.

## PM/PO delivery intelligence (Phase 5.1)

Phase 5.1 adds the metrics project managers and product owners actually ask for. It stands
on two foundations: a **forward-only metrics time-series** (`repository_metrics_snapshots`,
one row per repo per day, appended on every recompute) and lightly **enriched capture**
(milestone due dates + totals, issue first-response, reopened count).

### Metrics

- **Flow** (`/flow`, `mnemosyne_get_flow_metrics`) — cycle/lead-time **percentiles**
  (p50/p85/p95) for issue resolution and PR merge, WIP counts, aging buckets
  (0–7 / 7–30 / 30–90 / 90+ days), and untriaged backlog (open issues with no label/assignee).
  Percentiles answer "85% of issues close within N days" — a commitment you can make.
- **Throughput trend** (`/throughput`, `mnemosyne_get_throughput_trend`) — items closed per
  period and created-vs-closed net flow, over the time-series.
- **Backlog forecast** (`/forecast`, `mnemosyne_get_backlog_forecast`) — projected date the
  open backlog clears at the trailing close rate, or an explicit reason ("backlog growing",
  "insufficient history"). The projection is a linear estimate, not a Monte-Carlo model.
- **Work mix** (`/work-mix`, `mnemosyne_get_work_mix`) — issue counts by class
  (feature / bug / tech-debt / docs / other) via a configurable label→class map, plus bug ratio.
- **Quality** (`/quality`, `mnemosyne_get_quality_signals`) — bug ratio, reopened-issue rate,
  time-to-first-response percentiles.
- **Milestones** (`/milestones`, `mnemosyne_get_milestone_progress`) — percent complete and a
  projected completion date per milestone, flagged **at-risk** when the projection is past the
  due date.
- **Team load** (`/team-load`, `mnemosyne_get_team_load`) — open items per assignee, reviewer
  load, and a **bus factor** (smallest set of authors covering ≥ 50% of PRs). Reports
  distribution and concentration risk only — never a per-person performance score or ranking.
- **Delivery scorecard** (`/delivery-scorecard`, `mnemosyne_get_delivery_scorecard`) — the
  portfolio roll-up: median cycle, throughput direction, backlog trend, at-risk milestones.

### The forward-only caveat

The time-series is **not back-filled**: throughput, net-flow, forecast, and milestone
projection are empty until snapshots accumulate (a snapshot lands on every sync/webhook, so
in practice within a day or two). The UI shows "collecting history" rather than fabricating a
line, and the tools return a structured insufficient-history result. Everything that doesn't
need history — percentiles, aging, WIP, work-mix, quality, team-load — is available immediately.

### Label→class map (default, config-overridable)

`bug|defect|regression → bug`, `feature|enhancement → feature`,
`tech-debt|refactor|chore → tech_debt`, `docs|documentation → docs`, anything else → `other`.

## Not in this change

- Story points / estimates, GitHub Projects v2 sprints, individual performance ranking,
  cost attribution, external PM-tool (Jira/Linear) sync.
- Configurable scoring weights; dependency-freshness/CVE scanning.
