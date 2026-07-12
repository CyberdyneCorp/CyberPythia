# Intelligence web catch-up panels

## Why

Several intelligence features shipped with REST + MCP surfaces but no web UI
(deferred fast-follows): readiness regressions, organization vulnerabilities, and
the organization capability rollup. They were queryable by agents but invisible
on the dashboard.

## What changes

When an organization is selected, the Intelligence page gains:

- a **Readiness regressions** panel (repositories whose gate dropped, from/to gate + date),
- a **Vulnerabilities** panel (repositories with open critical/high Dependabot alerts + org totals),
- an **organization Capabilities** card (capability areas, repo count, total open bugs).

The existing readiness panel additionally shows, for READY repositories, what they
are missing to reach DONE (the org readiness rows now carry `missing_for_done`).

## Impact

- Backend: org readiness rows include `missing_for_done` (additive).
- Web: three new org-scoped panels + a readiness-row enhancement on the
  Intelligence page; loaded via the existing org-detail load.
