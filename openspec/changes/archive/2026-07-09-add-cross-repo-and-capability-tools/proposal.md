# Add cross-repo, organization-scoped, and capability tools

## Why

Agents and PM/PO users could query one repository or the whole portfolio, but
nothing in between, and every "how is this organization / project doing" question
required orchestrating several calls. This change (retro-documenting work shipped
in PRs #17–#22) adds organization-scoped intelligence, cross-repository agent
tools, and capability/feature composites so a single call answers the common
questions — on MCP, REST, and the web UI alike.

## What changes

- **Organization-scoped intelligence** — the portfolio overview and delivery
  scorecard accept an optional organization filter, and a rollup
  (`get_organization_intelligence`) aggregates a whole org in one call
  (scored/total, average/median health, grade distribution, at-risk milestones,
  throughput directions).
- **Cross-repository agent tools** — global/organization search across
  documentation, code, and issues; portfolio- or org-wide stale issue/PR finders;
  a fuzzy repository resolver; a recent-activity feed; and a raw metrics snapshot.
- **Capability / feature composites** — one-call, LLM-free project and organization
  capability overviews (capabilities, documentation topics, bug count, issue/PR
  counts) and a grounded Markdown feature-document generator.
- **Web** — a global search page, an organization overview + activity/stale panels
  on the Intelligence page driven by a server-scoped org filter, and a
  Capabilities tab (with feature-document generation) on the repository detail.

## Impact

- Affected specs: `mcp-interface`, `rest-api`, `web-ui`, `engineering-intelligence`.
- Affected code: `CrossRepoService`, `CapabilitiesService`, org filters on
  `IntelligenceService.portfolio` / `DeliveryIntelligenceService.delivery_scorecard`,
  `build_org_intelligence`, `EmbeddingPort.search_global`/`search_code_global`
  (+ pgvector), MCP tools, intelligence/repositories REST routers, and the
  SvelteKit search page + Intelligence/repository-detail views.
- All read-only and additive; no data-model or auth-model change. Already shipped
  and deployed — this change reconciles the living specs with the code.
