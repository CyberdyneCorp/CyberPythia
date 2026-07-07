# Tasks: add-delivery-intelligence-pm

> Phase 5.1. Builds on Phase 5's IntelligenceService + metrics pipeline. Two foundations
> (metrics time-series; enriched capture) then the PM/PO analytics on top. Keep the domain
> pure; unit coverage > 90%; ruff + mypy --strict clean. Absent-not-zero everywhere:
> empty population / short history → `null` / insufficient-data, never a fabricated 0.

## 1. Foundation A — metrics time-series

- [ ] 1.1 `MetricsSnapshot` entity + `MetricsHistoryPort` (record/upsert-per-day, list-window, prune). Unit tests for the port contract via a fake.
- [ ] 1.2 `repository_metrics_snapshots` table + Postgres adapter (upsert on `(repository_id, date)`); Alembic migration. Integration test on real Postgres (append, same-day upsert, window read).
- [ ] 1.3 Wire snapshot append into `MetricsRecomputeService.recompute` (compact row: open/closed issues, open/merged PRs, throughput counters, median cycle, health overall). Unit test parity: recompute still writes the current row AND appends/updates today's snapshot.
- [ ] 1.4 Retention/downsampling (`prune`: daily ≤ 180d, weekly beyond) invoked from the worker, not the request path. Unit tests for the downsample rule.

## 2. Foundation B — enriched capture

- [ ] 2.1 `Milestone` entity + `MilestonePort`; `milestones` table + adapter + migration. `GitHubPort.list_milestones` + client method (recorded-fixture integration test). New sync step reconciles milestones. Unit + integration tests.
- [ ] 2.2 Issue capture: nullable `first_response_at` (first non-author comment timestamp, best-effort) + `reopened_count`; entity fields, model columns (same migration as 2.1), mapper, and sync population. Unit tests incl. undeterminable → null.

## 3. Domain analytics (pure)

- [ ] 3.1 `DeliveryStats`: `percentile(values, q)` (linear interpolation) + `{p50,p85,p95,n}`; aging-bucket helper `[0-7,7-30,30-90,90+]`; WIP; untriaged rule. Unit tests incl. empty → all-None and boundary buckets.
- [ ] 3.2 `WorkMixService.classify(labels)` with the documented label→class map (config-overridable); distribution + bug ratio. Unit tests per class + unmapped → other.
- [ ] 3.3 Trend + forecast helpers over the snapshot series: throughput/net-flow per period, trailing close-rate, `projected_days_to_clear` (None + reason when not shrinking / short history). Unit tests for growing/insufficient/clearing cases.
- [ ] 3.4 `MilestoneProgressService`: percent-complete, burn-up from series, projected completion vs `due_on`, at-risk flag. Unit tests incl. no-due-date and no-history.
- [ ] 3.5 `TeamLoadService`: per-assignee load, reviewer load, bus factor (min authors ≥ 50% of PRs); asserts no per-person score/ranking in output. Unit tests.
- [ ] 3.6 Quality signals: bug ratio, reopened-issue rate (excludes no-data repos), first-response percentiles. Unit tests incl. insufficient-data paths.

## 4. Application: DeliveryIntelligenceService

- [ ] 4.1 `DeliveryIntelligenceService` composing sections 3.x over persisted metrics + history + milestones: `flow`, `throughput`, `forecast`, `work_mix`, `quality`, `milestones`, `team_load`, `delivery_scorecard`. DTOs in `application/dto`. Unit tests with fakes incl. every insufficient-data branch.
- [ ] 4.2 Compose in `composition.py` (history port, milestone port, service).

## 5. Interfaces: MCP + REST

- [ ] 5.1 Register the eight `mnemosyne_*` delivery tools (bearer + entitlement, structured insufficient-data). Interface tests incl. unauthenticated + insufficient-history shape.
- [ ] 5.2 Extend the `intelligence` REST router with the eight delivery paths + schemas + mapping. Interface tests incl. unknown-id 404 and missing-entitlement 403.

## 6. Web: delivery dashboard + panel

- [ ] 6.1 Models + `IntelligenceApi` methods for the delivery endpoints. Keep renders keyed.
- [ ] 6.2 `DeliveryViewModel` (Svelte 5 runes, MVVM): portfolio scorecard + per-repo delivery; "collecting history" state when trends are empty. ViewModel unit tests.
- [ ] 6.3 Delivery view on `/intelligence` (throughput/net-flow + backlog forecast + work-mix + at-risk milestones, self-contained inline SVG charts) and a delivery panel on the repository detail page.

## 7. Docs, gate, deploy, verify

- [ ] 7.1 Docs: extend `docs/engineering-intelligence.md` (each PM/PO metric, the label map, forecasting method + its limits, forward-only history) and update README + `docs/mcp-consumers.md`.
- [ ] 7.2 Full gate: ruff, mypy --strict, unit ≥ 90%, integration, BDD, `openspec validate --all --strict`, `npm run build` + frontend tests, docker build. Deploy migration + code to Coolify. Verify live over REST + MCP + browser against the two indexed repos: flow percentiles, work-mix, team-load/bus-factor, milestone progress, and — once ≥ 2 snapshots exist — a throughput trend + backlog forecast. Add a BDD scenario for the flow endpoint.
