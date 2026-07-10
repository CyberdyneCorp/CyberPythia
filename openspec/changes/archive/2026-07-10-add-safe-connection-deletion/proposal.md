# Safe connection deletion

## Why

Deleting a GitHub connection cascade-deletes every repository indexed under it —
docs, issues, PRs, code chunks, embeddings — with no warning and no way to gauge
the impact. In practice this silently wiped a 50-repo organization during an
unrelated App-reconnection. The frontend also swallowed any delete error, so a
failure (or a timeout on a large cascade) looked like "nothing happened".

## What changes

Keep the destructive semantics (delete removes the credential and its indexed
data) but make deletion **safe and observable**:

- **Impact preview** — the connection list reports `repository_count` so the UI
  and callers can see how much data a delete destroys.
- **Typed confirmation** — the web UI requires the operator to type the
  connection's owner before the Delete button arms, and states how many
  repositories will be destroyed.
- **Asynchronous deletion** — `DELETE` marks the connection `deleting`, enqueues
  a worker job, and returns `202`. The worker performs the cascade off the
  request path so a large connection can't hit the gateway timeout. The row
  shows `deleting` until the worker removes it.
- **Error surfacing** — the connections view reports delete failures instead of
  swallowing them.

## Impact

- Data model: new `ConnectionStatus.DELETING`; no schema/migration change (the
  existing `ON DELETE CASCADE` is reused, now executed in the worker).
- REST: `DELETE /github/connections/{id}` becomes `202` + `{repository_count}`;
  connection responses gain `repository_count`.
- Worker: new `delete_connection` job.
- Web: typed-confirmation delete affordance + error surfacing.
