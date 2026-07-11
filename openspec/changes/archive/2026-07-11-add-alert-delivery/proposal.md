# Alert delivery and digests

## Why

Mnemosyne computes plenty of "needs attention" signals — readiness regressions,
stale issues/PRs, at-risk milestones — but they are all **pull-only**. Nobody is
told; a repo silently slipping READY→MVP or a milestone going at-risk is only
seen if someone happens to query. The alerts don't alert anyone.

## What changes

Assemble a per-organization **digest** of the already-computed signals and both
expose it (pull) and deliver it (push):

- **Digest** — `DigestService.build(org)` gathers readiness regressions, the
  oldest stale issues/PRs, and at-risk milestones into one payload with a
  human-readable summary line.
- **Deliver** — when an outbound webhook is configured, the daily scheduled run
  POSTs each enabled org's non-empty digest to it (generic JSON with a `text`
  summary, Slack-compatible). Delivery is best-effort and never fails the run.
- **Pull** — `GET /intelligence/organizations/{org}/digest` and an MCP tool
  return the same digest on demand.

## Impact

- Config: `ALERT_WEBHOOK_URL`, `ALERT_DIGEST_ENABLED`.
- New `NotifierPort` + HTTP webhook adapter; `DigestService` (reuses readiness,
  cross-repo stale finders, delivery milestones).
- Worker: daily digest send after readiness recording.
- REST + MCP: organization digest.
