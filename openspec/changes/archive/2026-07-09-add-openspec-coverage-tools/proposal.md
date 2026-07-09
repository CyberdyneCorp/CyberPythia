# Add OpenSpec coverage tools

## Why

Teams driving spec-driven development want to see, per organization, which
repositories already have OpenSpec and which don't — to target adoption. Today an
agent or PM would have to inspect each repository's capabilities individually.

## What changes

- A composite computes an organization's **OpenSpec coverage**: its indexed
  repositories partitioned into those **with** OpenSpec and those **missing** it,
  using the canonical `has_openspec` signal (indexed OpenSpec changes or an
  OpenSpec-type document, from the latest sync), plus a coverage ratio.
- MCP: `mnemosyne_list_repositories_with_openspec(organization)` and
  `mnemosyne_list_repositories_missing_openspec(organization)`.
- REST: `GET /api/v1/intelligence/organizations/{org}/openspec-coverage` returning
  both lists + totals + coverage.

## Impact

- Affected specs: `mcp-interface`, `rest-api`.
- Affected code: `CapabilitiesService.organization_openspec_coverage`; two MCP tools;
  one REST endpoint. Read-only, additive; reuses the existing metrics `has_openspec`.
- Repositories not yet synced have no `has_openspec` signal and are reported under
  "missing" with a null `last_synced_at` so consumers can distinguish "no OpenSpec"
  from "not yet indexed".
