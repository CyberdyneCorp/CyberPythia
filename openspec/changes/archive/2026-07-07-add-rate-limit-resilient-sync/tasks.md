# Tasks: add-rate-limit-resilient-sync

> Behavioural resilience for the nightly fan-out. Typed; unit coverage > 90%; ruff + mypy
> --strict clean. Reuse the queue, trigger_sync, and the GitHub client.

## 1. Queue defer + trigger_sync

- [x] 1.1 `QueuePort.enqueue` gains `defer_seconds: float = 0.0`; `ArqQueueAdapter.enqueue` passes `_defer_by=timedelta(seconds=defer_seconds)` when > 0. `RepositoryUseCases.trigger_sync` gains `defer_seconds: float = 0.0`, threaded to enqueue. Unit tests (fake queue records defer).

## 2. Staggered scheduled fan-out

- [x] 2.1 `ScheduledSyncService.run()` enqueues repo i with `defer_seconds = i * stagger`; `scheduled_sync_stagger_seconds` config (default 5.0). Unit test: increasing defers, all repos enqueued, stagger=0 -> no defer.

## 3. Bounded rate-limit wait in the GitHub client

- [x] 3.1 `GitHubRateLimitError` in github_port. Client `_request`: on 403/429 rate-limit, compute wait from `Retry-After` (seconds) or `X-RateLimit-Reset`; if wait <= `max_wait_seconds` wait+retry (bounded by max_rate_limit_waits), else raise `GitHubRateLimitError`. Constructor `max_wait_seconds` (default 60). Unit tests (respx): short reset waits+retries, long reset raises fast, Retry-After honoured, non-rate-limit 403 unaffected.
- [x] 3.2 Config `github_rate_limit_max_wait_seconds: int = 60`; wire into the client in composition.

## 4. Docs, gate, deploy, verify

- [x] 4.1 Docs: note the stagger + bounded-wait env vars and the fail-fast-then-retry behaviour in `docs/deploy-coolify.md`.
- [ ] 4.2 Full gate: ruff, mypy --strict, unit >= 90%, integration, `openspec validate --all --strict`, docker build. Deploy worker. Verify config loads.
