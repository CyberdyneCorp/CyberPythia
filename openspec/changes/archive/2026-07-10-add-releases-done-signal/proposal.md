# GitHub Releases as a DONE readiness signal

## Why

The readiness classifier's DONE gate is meant to mean "production-grade / GA",
but it never considered whether a project has actually shipped a release —
because releases weren't indexed. In practice no repository can meaningfully
signal GA without it. This was the top deferred item from the readiness work.

## What changes

Capture whether a repository has any published GitHub Release during sync, store
it in the repository's metrics snapshot (no schema change), and add `releases` as
a required DONE check. DONE now additionally requires at least one published
release, on top of READY + dependency manifest + monitoring + SECURITY doc + low
open-bug ratio. Like every other check, `releases` reports `met` / `missing` /
`unknown` (unknown when the signal wasn't captured).

Release capture happens in the metrics sync step (one lightweight GitHub call,
valid for both PAT and App installation tokens). Incremental (webhook) syncs
preserve the last captured value rather than clobbering it.

## Impact

- Data model: `has_releases` added to the metrics summary snapshot (JSON) — no
  migration.
- Sync: metrics step fetches release presence; `MetricsRecomputeService`
  preserves it when a caller doesn't supply it.
- Readiness: new `releases` DONE check across the domain rule, MCP, REST, web.
