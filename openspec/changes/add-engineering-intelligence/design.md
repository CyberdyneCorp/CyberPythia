# Design: add-engineering-intelligence

## Context

Builds on the shipped core, Phase 3 (code context), and Phase 4 (webhooks), all deployed and verified on real data. The substrate Phase 5 needs already exists and stays fresh:

- `repository_metrics` (one row per repo): `issue_metrics`, `pr_metrics`, and a `summary` (has_readme/has_docs/has_openspec, document/openspec counts, open/closed issues, open/merged PRs, avg resolution/merge times), recomputed on every full sync **and** every incremental webhook via `MetricsRecomputeService`.
- `IssueMetricsService` / `PullRequestMetricsService` (pure): resolution/merge times, stale lists, `by_label`/`by_assignee`/`by_reviewer`/`by_author` maps, PR size distribution — all following the **absent-not-zero** rule (empty population → `None`).
- `FileRepository.list_by_repository` → `SourceFile` paths (for modes that capture a file tree).
- Repository entity: `enabled`, `archived`, `indexing_mode`, `last_synced_at`, `primary_language`.

Constraints unchanged: hexagonal, pure domain, `uv`/`just`, unit coverage > 90%, ruff + mypy --strict. Phase 5 adds **no** new GitHub or embedding calls and (in this change) **no** new tables — it is a compute/aggregation layer over persisted data.

## Goals / Non-Goals

**Goals**
- A transparent, weighted repository **health score** (0–100 + grade + findings) derived from existing metrics + file-tree signals.
- Delivery / backlog / review-bottleneck / maintenance-risk analytics per repo.
- Cross-repo **portfolio** aggregation (activity, risk, health leaderboard) + compare + onboarding summary.
- Expose all of it over MCP + REST + a Svelte dashboard, behind existing auth.

**Non-Goals**
- Historical trend lines / regression alerts (needs a snapshot time series — follow-up 5.1).
- Configurable scoring weights via UI; dependency-freshness/CVE scanning; people/org-chart analytics.

## Decisions

### D1. Health computed on-demand from persisted metrics — no new table
`RepositoryHealthService.score(summary, issue_metrics, pr_metrics, signals, now)` is a **pure** function of one repository's already-persisted metrics plus file-tree signals. There is no `repository_health_snapshots` table in this change: the inputs are already recomputed on every sync/webhook, so on-demand scoring is always as fresh as the last sync and costs one CPU pass. Callers that want caching key on `(repository_id, repository_metrics.computed_at)`.
- *Why not persist snapshots now*: trends are an explicit non-goal; adding a time series is a separable, additive follow-up that doesn't change the scoring contract.

### D2. Repository signals are their own pure service, with `unknown` ≠ `false`
`RepositorySignalsService.detect(paths: list[str], mode) -> RepositorySignals` derives boolean-or-unknown presence flags from captured file paths:
- `has_ci`: any of `.github/workflows/*.yml|yaml`, `.gitlab-ci.yml`, `.circleci/config.yml`, `azure-pipelines.yml`, `Jenkinsfile`.
- `has_tests`: a `tests?/` or `__tests__/` dir, or files matching `*_test.*` / `test_*.*` / `*.spec.*` / `*.test.*`.
- `has_dependency_manifest`: `package.json`, `pyproject.toml`, `requirements*.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle`, `Gemfile`.
- `has_contributing`, `has_license`: `CONTRIBUTING*`, `LICENSE*`.

When `mode` does not include a file tree (`docs_only`, `project_intelligence`), signals are `None` (**unknown**), and the health service excludes unknown components from the weighted score rather than penalising them as absent. This keeps scores honest across indexing modes and is the same absent-not-zero discipline the metrics services already use.

### D3. Health score: weighted components, each independently `null`-able, transparent inputs
Components (each 0–100 or `None` when its inputs are absent/unknown):
- **documentation** — README + docs presence + (bonus) OpenSpec adoption.
- **delivery** — normalised from median PR merge time + merge rate + median issue resolution time (faster/higher → higher).
- **maintenance** — inverse of stale-issue/PR accumulation relative to open counts.
- **testing_ci** — from `has_tests` + `has_ci` signals (skipped when unknown).
- **activity** — recency of `last_synced_at` / newest issue/PR relative to `now`.

`overall = weighted mean of the present components` (weights are documented constants; a component that is `None` drops out and the remaining weights renormalise). Grade: A ≥ 90, B ≥ 75, C ≥ 60, D ≥ 40, else F. The result object carries, for every component, its raw inputs and weight, and a ranked `findings: list[HealthFinding]` (severity + human message + the metric that triggered it) so the score is explainable, never a black box.
- *Why renormalise instead of impute*: a docs-only repo shouldn't score 0 on testing_ci it was never asked to capture; excluding the component is the honest reading.

### D4. Analytics services live in the application layer over the metrics store
The heavier rollups read persisted metrics through existing ports and shape DTOs; the *judgement* (thresholds, ranking) stays in small pure helpers so it is unit-testable:
- **delivery** — cycle/lead time, PR size distribution, throughput (from `pr_metrics`/`issue_metrics`).
- **backlog** — open-issue accumulation, stale count, open/closed ratio, oldest-open age.
- **review-bottlenecks** — PRs with slow/absent first review, reviewer-load concentration (Gini-style top-share over `by_reviewer`).
- **maintenance-risk** — a composite flag set: archived-but-enabled, no CI, no tests, stale-heavy, `last_synced_at` old, high open-issue backlog → a risk level + reasons.

### D5. Portfolio aggregation reads all metrics rows once, ranks in pure code
`PortfolioIntelligenceService` loads every enabled repository + its metrics row (a single batched read — `MetricsStore.list_all()` / `RepositoryRepository.list_enabled()`), then a pure aggregator produces: health-ranked leaderboard, most-active (by recent issue/PR/merge volume), abandoned (no activity within a window), and bug-heavy (top `by_label` "bug"/"defect" counts). `compare_repositories(ids)` is the same scoring applied to a chosen subset, aligned into a comparison table. `generate_onboarding_summary(id)` composes health + `summary` + repository-structure explanation (reusing the existing structure use case) into a newcomer brief.

### D6. Interfaces mirror the existing patterns exactly
- **MCP**: eight `mnemosyne_*` tools registered like the current ones, returning JSON dicts, behind the same bearer + entitlement guard. Absent metrics → a structured "not yet synced / mode does not capture X" message, never a 500.
- **REST**: an `intelligence` router (`/api/v1/intelligence/...`) under `AdminCaller`/entitlement, DTOs via the existing schema + mapping conventions.
- **Web**: an `IntelligenceViewModel` (MVVM, Svelte 5 runes) feeding a `/intelligence` dashboard route (portfolio) and a health panel embedded on the repository detail page. All list renders keyed (guarding against the `each_key_duplicate` class of bug hit earlier).

### D7. Absent-not-zero is a first-class contract everywhere
Every score, average, and rate is `None` (surfaced as "—"/"insufficient data") when its population is empty, and the UI/tools say *why* (not synced yet, mode doesn't capture it, no PRs merged). A repo with zero merged PRs is "no delivery data", not "delivery score 0". This is the single rule that keeps the intelligence trustworthy.

## Risks / Trade-offs

- **Scoring is opinionated.** Mitigation: weights are documented constants and every component exposes its inputs, so a reader can see exactly why a score is what it is; making weights configurable is a named follow-up.
- **Signals depend on indexing mode.** A `docs_only` repo yields `unknown` CI/tests; the renormalising score + explicit "unknown" labelling prevents misleading penalties.
- **On-demand vs. cached.** Portfolio over hundreds of repos is one summarised row each; if it ever gets heavy, the `(repo, computed_at)` cache key makes memoisation trivial without changing the contract.

## Migration / Rollout

No migration. Purely additive endpoints/tools/UI. Ships behind the existing auth + entitlement; enabling the dashboard route is a frontend deploy. Verified against the two live-indexed repos (CyberdyneAuth, CyberPythia) end-to-end over REST + MCP + browser.
