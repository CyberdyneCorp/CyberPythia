# Tasks: add-engineering-intelligence

> Builds on the shipped core + Phase 3 + Phase 4. This is a read/compute/aggregation layer over the existing `repository_metrics` rows, issue/PR metric services, and captured file tree — **no new GitHub calls, no migration**. Keep the domain pure; unit coverage > 90%; ruff + mypy --strict clean. Honour absent-not-zero everywhere (empty population → `null`/`unknown`, never a fabricated 0).

## 1. Domain: signals + health scoring (pure)

- [x] 1.1 `RepositorySignals` value object + `RepositorySignalsService.detect(paths, mode)` — `has_ci`/`has_tests`/`has_dependency_manifest`/`has_contributing`/`has_license` as `bool | None` (None = unknown when the mode captures no tree). Unit tests: each detector positive/negative, and all-unknown for tree-less modes.
- [x] 1.2 Health value objects: `ComponentScore` (name, score `float | None`, weight, inputs), `HealthFinding` (severity, message, metric), `RepositoryHealth` (components, overall `float | None`, grade, findings).
- [x] 1.3 `RepositoryHealthService.score(summary, issue_metrics, pr_metrics, signals, now)` — documentation/delivery/maintenance/testing_ci/activity components, renormalising weighted overall (None components drop out), grade thresholds (A≥90…F), ranked findings. Unit tests: fully-populated, missing-component renormalisation, never-synced → insufficient, grade boundaries, findings content.
- [x] 1.4 Pure ranking/threshold helpers reused by analytics (reviewer-load concentration, abandoned/active windows, risk-level rules). Unit tests for each threshold edge.

## 2. Application: analytics services

- [x] 2.1 `MetricsStore` port gains `list_all()` (batched read of every repository_metrics row) + Postgres adapter method. Integration test on real Postgres.
- [x] 2.2 `DeliveryAnalytics`, `BacklogAnalytics`, `ReviewBottleneckAnalytics`, `MaintenanceRiskAnalytics` — per-repo DTO builders over persisted metrics + signals; absent-not-zero. Unit tests with fakes incl. empty-population cases.
- [x] 2.3 `PortfolioIntelligenceService` — load enabled repos + metrics once, produce leaderboard / most-active / abandoned / bug-heavy; repos without metrics carried with an insufficient-data marker. `compare(ids)` + `generate_onboarding_summary(id)` (reuse the existing repository-structure use case). Unit tests.
- [x] 2.4 Wire signals: a small helper loads a repo's file-tree paths via `FileRepository.list_by_repository` and feeds `RepositorySignalsService`; health/risk use it. Unit test.

## 3. Interfaces: MCP + REST

- [x] 3.1 Register the eight `mnemosyne_*` intelligence tools in the MCP server (bearer + entitlement guard, structured insufficient-data results). Unit/interface tests incl. unauthenticated rejection + insufficient-data shape.
- [x] 3.2 `intelligence` REST router (`/api/v1/intelligence/...`): portfolio, per-repo health/delivery/backlog/review-bottlenecks/maintenance-risk/onboarding, compare. Schemas + mapping. Interface tests incl. unknown-id 404 and missing-entitlement 403.
- [x] 3.3 Compose services in `composition.py`; register the router in `main.py`; confirm openapi lists the new paths.

## 4. Web: intelligence dashboard + health panel

- [x] 4.1 Models + API client: `RepositoryHealth`, `PortfolioOverview`, delivery/backlog/risk types; `IntelligenceApi` methods. Keep list renders keyed.
- [x] 4.2 `IntelligenceViewModel` (Svelte 5 runes, MVVM): load portfolio + per-repo health; busy/error state. ViewModel unit tests.
- [x] 4.3 `/intelligence` dashboard route (leaderboard, most-active, abandoned, bug-heavy) + health panel on the repository detail page (score, grade, components, findings; not-applicable for unknown components). Nav link.

## 5. Docs, gate, deploy, verify

- [x] 5.1 Docs: `docs/engineering-intelligence.md` (what each score/metric means, weights, absent-not-zero, the eight tools + endpoints); update README + `docs/mcp-consumers.md`.
- [x] 5.2 Full gate: ruff, mypy --strict, unit ≥ 90%, integration, BDD, `openspec validate --all --strict`, `npm run build` + frontend tests, docker build. Deploy to Coolify. Verify live over REST + MCP + browser against the two indexed repos (CyberdyneAuth, CyberPythia): health score + grade, portfolio overview, a bottleneck/risk read, and the dashboard render. Add a BDD scenario for the health endpoint.
