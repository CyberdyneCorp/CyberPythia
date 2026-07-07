# Proposal: add-delivery-intelligence-pm

## Why

Phase 5 scores repository *health* and rolls repos into a portfolio, but it answers
those questions with point-in-time **medians**. Project managers and product owners
ask a different, sharper set of questions that medians can't answer:

- **"Is delivery predictable?"** — not the median cycle time, but "85% of issues close
  within N days" (a number you can commit to a stakeholder).
- **"Is the backlog under control?"** — are we closing work faster than it arrives, and
  *when* will the backlog clear at the current rate?
- **"Where is effort actually going?"** — feature vs. bug vs. tech-debt vs. docs, so
  investment can be defended against the roadmap.
- **"When will this milestone ship?"** — burn-up and a projected completion date.
- **"Who's overloaded, and where's the single-point-of-failure risk?"**

Phase 5.1 delivers the full PM/PO metric set. It splits into three parts by cost:
a large tranche is **computable today** from the metrics Mnemosyne already stores; the
rest is unlocked by two small foundations — a **metrics time-series** (for anything
"over time" or "forecast") and a little **enriched capture** (milestone due dates,
first-response and reopen signals). The absent-not-zero discipline carries through:
every metric is `null`/"insufficient data" when its population is empty, never a
fabricated zero.

## What Changes

### Foundation A — metrics time-series (unlocks all trends & forecasts)
- A `repository_metrics_snapshots` table: on every metrics recompute (full sync and each
  webhook), append a compact row (open/closed counts, throughput counters, cycle-time
  aggregates, health overall, timestamp). This is the single change that unlocks
  throughput trends, net-flow-over-time, backlog burndown/forecast, and health trend.
- A retention/downsampling policy (keep daily points; coarse-grain older than 180 days).

### Foundation B — enriched capture (small additions to the existing sync)
- **Milestones**: capture GitHub milestones as first-class records (title, state, due_on,
  open/closed issue counts) so milestone **burn-up** and **projected completion** are real.
  (`Issue.milestone` name is already captured; this adds the milestone's due date + totals.)
- **First-response time**: capture the timestamp of an issue's first non-author comment, so
  *responsiveness* (time-to-first-response) is distinct from time-to-resolution.
- **Reopened count**: capture how many times an issue was reopened, for a quality signal.

### Metrics — computable now (no new capture)
- **Cycle/lead-time percentiles** — p50/p85/p95 for issue resolution, PR merge, and
  time-to-first-review (predictability, not just central tendency).
- **Aging work-in-progress** — open issues/PRs bucketed by age (0–7d / 7–30d / 30–90d / 90d+).
- **WIP** — count of in-flight issues/PRs (Little's-Law input alongside cycle time).
- **Untriaged backlog** — open issues with no label and/or no assignee (grooming debt).
- **Work-mix** — effort split by label class (feature / bug / tech-debt / docs / other) via
  a configurable label→class map.
- **Bug ratio** — bug-class issues as a share of all issues.
- **Team load** — open items per assignee (overload), and **bus factor** / authorship
  concentration (single-point-of-failure risk) from the captured author/reviewer maps.
- **Review SLA breaches** — open PRs waiting on first review beyond a threshold (count + list).
- **Net flow (current window)** — issues/PRs created vs. closed in the last N days.

### Metrics — unlocked by the foundations
- **Throughput trend** & **net-flow trend** — closed-per-week and created-vs-closed over time (Foundation A).
- **Backlog forecast** — projected date the open backlog clears at the trailing close rate (A).
- **Health / cycle-time trend** with regression flags (A).
- **Milestone progress** — % complete, burn-up, and projected completion vs. `due_on` (B).
- **Time-to-first-response** percentiles (B) and **reopened-issue rate** (B).

### Surfaces
- **MCP tools** (new): `mnemosyne_get_flow_metrics`, `mnemosyne_get_throughput_trend`,
  `mnemosyne_get_backlog_forecast`, `mnemosyne_get_work_mix`, `mnemosyne_get_quality_signals`,
  `mnemosyne_get_milestone_progress`, `mnemosyne_get_team_load`, and a portfolio-level
  `mnemosyne_get_delivery_scorecard`.
- **REST endpoints** (new): the same under `/api/v1/intelligence/repositories/{id}/...`
  (`flow`, `throughput`, `forecast`, `work-mix`, `quality`, `milestones`, `team-load`) plus
  `/api/v1/intelligence/delivery-scorecard`.
- **Web**: a **Delivery** view on the Intelligence dashboard (throughput/net-flow charts,
  backlog forecast, work-mix breakdown, milestone burn-up) and a per-repo delivery panel.

### Non-goals (future changes)
- Story-point / estimate ingestion and estimate-vs-actual (GitHub has no native points;
  would require a label or Projects-field convention). Work-mix uses issue *counts*, not points.
- GitHub **Projects (v2)** board/iteration/sprint modelling — milestones are the unit here.
- Per-person productivity ranking or any individual performance scoring (team-load reports
  *distribution and risk*, never ranks people).
- Monetary/cost attribution and external PM-tool (Jira/Linear) sync.

## Capabilities

### New Capabilities
- `delivery-intelligence`: PM/PO delivery analytics (percentiles, WIP/aging, work-mix,
  quality, team-load) and — over the metrics time-series — throughput/net-flow trends,
  backlog forecasting, and milestone burn-up.
- `metrics-history`: the append-only metrics snapshot time-series + retention policy.

### Modified Capabilities (additive deltas)
- `repository-sync`: ADDED — milestone records, issue first-response timestamp, reopened count.
- `mcp-interface`: ADDED — the eight PM/PO delivery tools.
- `rest-api`: ADDED — the delivery/flow/forecast/work-mix/quality/milestone/team-load endpoints.
- `web-ui`: ADDED — the Delivery dashboard view + per-repo delivery panel.

## Impact
- **Data model**: `repository_metrics_snapshots` (time-series) and `milestones`; new nullable
  columns on issues (`first_response_at`, `reopened_count`). One Alembic migration.
- **Code**: history port + snapshot writer wired into `MetricsRecomputeService`; new pure
  analytics (percentiles, aging, work-mix, forecast, milestone burn-up, bus factor) behind
  the existing hexagonal seams; MCP tools, REST router additions, and Svelte Delivery view.
- **Dependencies**: none new (pure-Python statistics; forecasting is linear trailing-rate).
- **Security**: read-only, behind the existing bearer + `mnemosyne` entitlement; team-load
  reports distribution/risk only — no individual performance scoring, and no data a caller
  couldn't already read via the per-repo tools.
- **Performance**: snapshot rows are tiny and written on the existing recompute path; trend
  and forecast reads scan one repo's time-series (bounded by retention). Point analytics are
  CPU-only over already-loaded metrics.
- **Migration/rollout**: additive. Trends start accumulating from first deploy (history is
  forward-only); back-fill is out of scope. Milestone/first-response/reopen metrics populate
  on the next sync of each repo.
