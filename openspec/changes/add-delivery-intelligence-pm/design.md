# Design: add-delivery-intelligence-pm

## Context

Builds on Phase 5 (`add-engineering-intelligence`, deployed & verified). Phase 5's
`IntelligenceService` reads the per-repo `repository_metrics` row (issue/PR metric
dataclasses + summary) computed by `MetricsRecomputeService` on every full sync and each
webhook. The issue/PR entities already carry what most PM/PO point-metrics need:

- Issue: `state`, `labels`, `assignees`, `milestone` (name), `created_at`, `updated_at`,
  `closed_at`, `comments_count`, `resolution_time_seconds`.
- PR: `merged`, `reviewers`, `created_at`, `merged_at`, `first_review_at`, `additions`,
  `deletions`, `changed_files`, `review_decision`, `time_to_first_review_seconds`.

What is missing is (1) any **history** — every metric is the latest snapshot only — and
(2) three capture fields: milestone **due date + totals**, issue **first-response**
timestamp, and **reopened** count. Phase 5.1 adds those two foundations and the analytics
on top. Constraints unchanged: hexagonal, pure domain, `uv`/`just`, unit coverage > 90%,
ruff + mypy --strict, absent-not-zero.

## Goals / Non-Goals

**Goals**
- The full PM/PO metric set: predictability (percentiles), flow (WIP/aging/net-flow),
  throughput trend + backlog forecast, work-mix, quality signals, milestone burn-up,
  team-load/bus-factor.
- Two minimal, reusable foundations (metrics time-series; enriched capture) that unlock the
  "over time" and milestone metrics without reshaping the pipeline.

**Non-Goals**
- Story points/estimates, GitHub Projects v2 sprints, individual performance ranking,
  cost attribution, external PM-tool sync (see proposal Non-goals).

## Decisions

### D1. Metrics time-series as an append-only snapshot, written on the existing recompute
`MetricsRecomputeService.recompute` already runs on every sync and webhook and writes the
current `repository_metrics` row. Phase 5.1 has it **also append** a compact
`repository_metrics_snapshots` row: `(repository_id, captured_at, open_issues,
closed_issues, open_prs, merged_prs, throughput_issues, throughput_prs, median_cycle_seconds,
health_overall)`. Reads for trends/forecast scan one repo's series.
- *Append, not recompute-from-events*: we don't have full event history, and forward-only
  snapshots are cheap, correct going forward, and match how teams actually track trend.
- *Idempotency*: at most one snapshot per repo per UTC day — a same-day recompute updates
  that day's row (upsert on `(repository_id, date)`), so bursty webhooks don't inflate the series.
- *Retention* (`MetricsHistoryPort.prune`): keep daily points ≤ 180 days, weekly beyond;
  invoked opportunistically from the worker, not on the request path.

### D2. Enriched capture is additive and degrades cleanly
- **Milestones**: a `milestones` table (`repository_id, number, title, state, due_on,
  open_issues, closed_issues, updated_at`) populated by a new sync step that lists the repo's
  milestones. `Issue.milestone` (name) already links issues to them; burn-up joins on it.
- **First-response**: capture the first non-author comment timestamp per issue
  (`issues.first_response_at`). When the sync can't determine it (older data, no comments),
  it stays `NULL` and the metric reports insufficient data for that issue.
- **Reopened count**: `issues.reopened_count` from the issue's event/timeline; absent → 0
  is acceptable here (a count, not an average), but the *rate* excludes repos with no data.
- Every new field is nullable; a repo synced before this change simply shows the metric as
  insufficient-data until its next sync.

### D3. Percentiles and forecasting are pure functions
- **Percentiles**: `percentile(values, q)` via linear interpolation (p50/p85/p95) over the
  existing per-issue/PR durations. A `DeliveryStats` domain helper returns
  `{p50, p85, p95, n}` or all-`None` when `n == 0`.
- **Aging buckets**: pure bucketing of open-item ages into `[0-7, 7-30, 30-90, 90+]` days.
- **Backlog forecast**: trailing close-rate (from the snapshot series, e.g. mean
  issues-closed/week over the last K weeks) applied to current open count →
  `projected_days_to_clear` + a date; `None` when the rate is ≤ 0 (backlog not shrinking) or
  history is too short, with an explicit reason ("backlog growing", "insufficient history").
- **Bus factor**: smallest set of authors covering ≥ 50% of authored PRs; a low number on a
  busy repo = concentration risk.
- All judgement (thresholds, class maps, windows) lives in pure helpers extended from Phase 5's
  `intelligence_rules`, so it is unit-testable without I/O.

### D4. Work-mix uses a configurable label→class map, counts not points
`WorkMixService.classify(labels)` maps each issue to `feature | bug | tech_debt | docs | other`
via a documented default map (`bug|defect|regression → bug`, `feature|enhancement → feature`,
`tech-debt|refactor|chore → tech_debt`, `docs|documentation → docs`), overridable by config.
Work-mix reports the distribution of **issue counts** across classes (the honest unit; points
are a non-goal). Bug ratio is the `bug` share.

### D5. Team-load reports distribution and risk, never ranks people
`TeamLoadService` returns open-items-per-assignee and reviewer-load from the existing
`by_assignee`/`by_reviewer`/`by_author` maps, plus bus factor. It surfaces **overload and
single-point-of-failure risk** (e.g. "1 author owns 80% of PRs") — it deliberately produces no
per-person score or ranking, to keep the tool safe for a management context.

### D6. Milestone progress = burn-up + projection
`MilestoneProgressService` per milestone: `% complete = closed/(open+closed)`, a burn-up from
the snapshot series (closed-over-time), and `projected_completion` = now + (open ÷ trailing
close-rate), flagged **at risk** when the projection is past `due_on`. No history or no close
rate → progress only, projection `None` with a reason.

### D7. Surfaces mirror Phase 5 exactly
New tools/endpoints follow the Phase 5 shapes (bearer + `mnemosyne` entitlement, structured
insufficient-data results, `translate_error` for unknown ids). The web **Delivery** view is a
new tab on `/intelligence` with small inline SVG charts (no new chart dependency — the CSP on
the artifact/self-hosted bundle forbids external libs anyway) and a per-repo delivery panel.

## Risks / Trade-offs
- **History is forward-only.** Trends/forecasts are empty until snapshots accumulate; the UI
  says "collecting — check back in a few days" rather than faking a back-fill. Documented, accepted.
- **Forecasting is deliberately simple** (linear trailing-rate). It is labelled an estimate with
  its inputs shown; no Monte-Carlo/AR models in this change.
- **First-response/reopened depend on comment/event capture** that costs extra GitHub calls per
  issue. Mitigation: capture first-response from the issue's existing comment data where present
  and treat it as best-effort (nullable), rather than fanning out a timeline call per issue.

## Migration / Rollout
One Alembic migration: `repository_metrics_snapshots`, `milestones`, and the two issue columns.
Additive and backward-compatible. Snapshots begin accruing on first deploy; milestone/first-
response/reopen metrics populate as each repo re-syncs. Verified end-to-end against the two
indexed repos over REST + MCP + browser, with the trend/forecast tools exercised once at least
two snapshots exist.
