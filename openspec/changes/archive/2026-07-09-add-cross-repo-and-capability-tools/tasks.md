# Tasks

_Retro-documents work already shipped and deployed in PRs #17–#22; all items done._

## 1. Organization-scoped intelligence (#17)
- [x] 1.1 `organization` filter on `IntelligenceService.portfolio` + `DeliveryIntelligenceService.delivery_scorecard`
- [x] 1.2 `build_org_intelligence` rollup + `mnemosyne_get_organization_intelligence` + org param on portfolio/scorecard tools
- [x] 1.3 REST: `?organization=` on portfolio/scorecard + `/organizations/{org}/intelligence`

## 2. Cross-repo tools (#18, #19)
- [x] 2.1 `CrossRepoService` (resolver, stale finders, recent activity, search)
- [x] 2.2 `EmbeddingPort.search_global`/`search_code_global` + pgvector impl (repository_id on matches)
- [x] 2.3 MCP: search_all, find_stale_issues/prs_across_repos, find_repositories, get_recent_activity, get_repository_metrics
- [x] 2.4 REST: `/intelligence/search`, `/stale-issues`, `/stale-prs`, `/recent-activity`, `/repos/find`

## 3. Capability / feature composites (#21)
- [x] 3.1 `CapabilitiesService` (repo + org capabilities)
- [x] 3.2 Shared `FEATURE_DOCUMENT_PROMPT` + feature-document via `ContextUseCases.ask`
- [x] 3.3 MCP: get_repository_capabilities, get_organization_capabilities, generate_feature_document
- [x] 3.4 REST: `/repos/{id}/capabilities`, `POST /repos/{id}/feature-document`, `/organizations/{org}/capabilities`

## 4. Web (#20, #21, #22)
- [x] 4.1 `/search` page (docs/code/issues/repositories, org scope, snippet+line for code)
- [x] 4.2 Intelligence: server-scoped org filter + org overview card + activity/stale panels
- [x] 4.3 Repository detail: Capabilities tab + feature-document generation

## 5. Tests
- [x] 5.1 MCP integration tests for all new tools; REST endpoint tests; pgvector global-search integration
- [x] 5.2 Web view-model tests + build
