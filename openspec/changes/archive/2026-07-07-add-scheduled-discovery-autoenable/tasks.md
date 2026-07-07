# Tasks: add-scheduled-discovery-autoenable

> Reuse discover + update_selection. Auto-enable ONLY newly-seen non-archived repos (never
> override manual disables). Pure/typed; unit coverage > 90%; ruff + mypy --strict clean.

## 1. Application

- [x] 1.1 `ScheduledDiscoveryService.run()` — snapshot existing github ids; for each connection run `discover`; recompute the repo set; enable each repo whose github id is new AND not archived, in `auto_enable_mode`, via `update_selection`; leave all pre-existing repos untouched. Return `{discovered, newly_enabled, skipped_archived}`. Unit tests: new repo enabled, pre-existing-disabled untouched, archived skipped, auto-enable-off no-ops, per-connection error does not abort.

## 2. Config + worker cron

- [x] 2.1 Config: `scheduled_discovery_enabled: bool = True`, `auto_enable_new_repos: bool = True`, `auto_enable_mode: str = "project_intelligence"`, `auto_enable_archived: bool = False`. Unit test defaults + env override + mode validation.
- [x] 2.2 Worker: the daily cron coroutine runs discovery+auto-enable (when enabled) BEFORE the full-sync fan-out; compose the service in the container. Unit test the ordering + that discovery is skipped when disabled.

## 3. Docs, gate, deploy, verify

- [x] 3.1 Docs: `docs/deploy-coolify.md` env vars + behaviour (auto-enable new non-archived repos in project_intelligence; respects manual disables); note the one-time bulk-enable is a separate admin action.
- [x] 3.2 Full gate: ruff, mypy --strict, unit >= 90%, integration, `openspec validate --all --strict`, docker build. Deploy worker. Verify the config loads + the cron chains discovery before sync. Perform the one-time admin bulk-enable of existing non-archived repos and confirm the daily sync then covers them.
