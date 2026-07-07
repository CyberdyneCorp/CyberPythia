# Proposal: add-rate-limit-resilient-sync

## Why

The nightly job now enqueues a full sync for ~238 enabled repositories at once, all hitting
GitHub with a **personal PAT capped at 5,000 requests/hour**. Two failure modes emerge at that
scale:

1. **Thundering herd** — 238 syncs start in a burst (4 concurrent), spiking the request rate and
   exhausting the hourly limit early in the run.
2. **Worker stall** — the GitHub client already backs off on a rate-limit response, but it sleeps
   until `X-RateLimit-Reset` **capped at a full hour, up to three times**. A repo that hits an
   exhausted primary limit therefore blocks a worker slot for up to ~1 hour (potentially ~3),
   and with only 4 slots a few such repos freeze the whole run.

Neither is graceful. This change smooths the request rate and bounds the wait so a rate-limited
repo **fails fast and is retried on the next daily run**, keeping the worker flowing.

## What Changes

- **Staggered fan-out** — `ScheduledSyncService` enqueues each repository's sync with an
  increasing delay (arq `defer_by`), spreading the run over a window instead of a burst. The
  stagger is configurable (`scheduled_sync_stagger_seconds`, default a few seconds → a ~240-repo
  run spreads over ~20 minutes). Per-repo locks and `max_jobs` still apply.
- **Bounded rate-limit wait** — the GitHub client honors `X-RateLimit-Reset` **and** `Retry-After`
  (secondary/abuse limits), but only waits up to a configurable cap
  (`github_rate_limit_max_wait_seconds`, default 60s). Short/secondary limits (the common case)
  are absorbed by a brief wait + retry; when the reset is further out than the cap, the client
  raises a distinct **`GitHubRateLimitError`** immediately rather than blocking the slot — the
  repo's sync fails cleanly and the next daily run picks it up.
- **Queue defer support** — `QueuePort.enqueue` (and the arq adapter) gain an optional
  `defer_seconds`; `RepositoryUseCases.trigger_sync` threads it through so callers can stagger.

### Non-goals (future changes)

- A global request-rate governor / token-bucket shared across worker jobs (staggering + per-call
  bounded wait are the lighter, sufficient mechanism here).
- Automatic mid-run rescheduling of rate-limited repos to a later time within the same night
  (they are simply retried on the next daily run).
- Changing the credential model (moving to an org fine-grained PAT / GitHub App for higher limits
  is the real capacity fix and is an ops action, not code).

## Capabilities

### Modified Capabilities (additive delta)

- `repository-sync`: ADDED — staggered scheduled fan-out and a bounded, fail-fast rate-limit wait.

## Impact

- **Data model**: none.
- **Code**: `defer_seconds` on the queue port/adapter + `trigger_sync`; stagger in
  `ScheduledSyncService`; bounded-wait + `Retry-After` + `GitHubRateLimitError` in the GitHub
  client; two config fields wired through composition.
- **Dependencies**: none new (`arq` already supports `_defer_by`).
- **Security**: none (behavioural resilience only).
- **Behaviour change**: the client no longer blocks up to an hour on an exhausted primary limit;
  it fails that call fast instead. This is intentional — it trades one repo's freshness this night
  for worker throughput and overall completion of the run.
- **Ops**: tune `SCHEDULED_SYNC_STAGGER_SECONDS` and `GITHUB_RATE_LIMIT_MAX_WAIT_SECONDS` if
  needed. The durable capacity fix remains swapping the personal PAT for an org fine-grained PAT
  or a GitHub App (higher hourly limits), which this change is designed to bridge until done.
