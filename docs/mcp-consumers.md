# MCP consumer guide

The MCP server (`mnemosyne-mcp`, streamable HTTP at `/mcp`) exposes the
Mnemosyne tool suite to agents. Every call requires a bearer token — either a
CyberdyneAuth token with the `mnemosyne` entitlement/audience, or a
**Mnemosyne API key** (`mnem_…`) generated in the web UI (Connections → API
keys). An API key is the simplest option: it does not expire on the CyberdyneAuth
schedule, you paste it straight into the `Authorization` header, and you revoke it
in the UI when done. API keys grant read/query access only (not admin).

## Connecting

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

transport = StreamableHttpTransport("https://mnemosyne-mcp.<domain>/mcp", auth=TOKEN)
async with Client(transport) as client:
    repos = await client.call_tool("mnemosyne_list_repositories", {})
```

Claude Code: `claude mcp add --transport http mnemosyne https://mnemosyne-mcp.<domain>/mcp --header "Authorization: Bearer <token>"`.

### One-click OAuth (claude.ai / Claude Desktop)

When the server has OAuth enabled (see deploy doc), DCR-capable clients connect
by pasting just the URL `https://mnemosyne-mcp.<domain>/mcp` — the client
registers itself, runs a browser login against CyberdyneAuth, and stores the
resulting token. No `--header` and no API key needed. The signed-in user must
hold the `mnemosyne` entitlement. Header-based clients (Claude Code, OpenAI,
`mcp-remote`) can keep using an API key or bearer against the same server — both
auth paths are live simultaneously.

## Tools

Repositories are addressed by full name (`owner/name`).

| Tool | Purpose |
| --- | --- |
| `mnemosyne_list_repositories` | indexed repositories + sync freshness |
| `mnemosyne_get_repository_summary` | metadata, docs presence, headline metrics |
| `mnemosyne_get_repository_tree` | file tree (mode `code_metadata`) |
| `mnemosyne_get_readme` / `mnemosyne_get_docs_index` | documentation |
| `mnemosyne_search_docs` | semantic search over docs |
| `mnemosyne_get_openspec_context` | OpenSpec changes (proposal/design/tasks) |
| `mnemosyne_list_issues` / `mnemosyne_get_issue` / `mnemosyne_search_issues` | issues |
| `mnemosyne_get_issue_resolution_metrics` | avg/median resolution, staleness |
| `mnemosyne_list_pull_requests` / `mnemosyne_get_pull_request` | PRs |
| `mnemosyne_get_pr_review_metrics` | merge time, first review, merge rate |
| `mnemosyne_find_stale_issues` / `mnemosyne_find_stale_prs` | staleness report |
| `mnemosyne_search_code` | semantic search over source code (code_context/full_context) |
| `mnemosyne_get_symbol_context` | look up chunks defining a symbol |
| `mnemosyne_get_file_content` | captured content of a source file by path |
| `mnemosyne_get_related_files` | files related via import/reference heuristics |
| `mnemosyne_explain_repository_structure` | tree, languages, important files, key symbols |
| `mnemosyne_build_context_pack` | task-specific context bundle |
| `mnemosyne_answer_from_repo_context` | grounded Q&A with citations |
| `mnemosyne_get_repository_health` | health score, grade, components, findings (Phase 5) |
| `mnemosyne_get_delivery_metrics` | cycle/lead time, PR size distribution, throughput |
| `mnemosyne_get_backlog_metrics` | open/stale backlog, ratios, oldest-open age |
| `mnemosyne_get_review_bottlenecks` | slow/absent-review PRs, reviewer-load concentration |
| `mnemosyne_get_maintenance_risk` | risk level (low/medium/high) with reasons |
| `mnemosyne_get_portfolio_overview` | cross-repo leaderboard, most-active, abandoned, bug-heavy (optional `organization` to scope) |
| `mnemosyne_compare_repositories` | aligned health + metric comparison |
| `mnemosyne_generate_onboarding_summary` | newcomer brief for a repository |
| `mnemosyne_get_flow_metrics` | cycle/lead percentiles, WIP, aging, untriaged (Phase 5.1) |
| `mnemosyne_get_throughput_trend` | items-closed and net-flow over the time-series |
| `mnemosyne_get_backlog_forecast` | projected backlog-clear date (or why there is none) |
| `mnemosyne_get_work_mix` | feature/bug/tech-debt/docs distribution + bug ratio |
| `mnemosyne_get_quality_signals` | bug ratio, reopened-issue rate, first-response percentiles |
| `mnemosyne_get_milestone_progress` | per-milestone burn-up + projected completion |
| `mnemosyne_get_team_load` | load per assignee, reviewer load, bus-factor risk |
| `mnemosyne_get_delivery_scorecard` | portfolio delivery roll-up (optional `organization` to scope) |
| `mnemosyne_get_organization_intelligence` | one-call org rollup: repos, scored, avg/median health, grade distribution, at-risk milestones, throughput directions |
| `mnemosyne_list_organizations` | organizations discovered, with total/indexed repo counts |
| `mnemosyne_list_organization_repositories` | all repositories in an org the credential can read |
| `mnemosyne_find_repositories` | fuzzy-resolve a vague name into exact `owner/name` |
| `mnemosyne_get_repository_metrics` | raw computed metrics snapshot (inputs behind the health/delivery tools) |
| `mnemosyne_search_all` | search across many repos at once — `kind` = docs \| code \| issues, optional `organization` |
| `mnemosyne_find_stale_issues_across_repos` | stale open issues across all repos (or one org), oldest first |
| `mnemosyne_find_stale_prs_across_repos` | stale open PRs across all repos (or one org), oldest first |
| `mnemosyne_get_recent_activity` | recently synced repos + latest updated issues/PRs (all repos or one org) |
| `mnemosyne_get_repository_capabilities` | one-call project overview: capabilities (OpenSpec areas), doc topics, **bug count**, issue/PR counts |
| `mnemosyne_get_organization_capabilities` | what an org can do right now: union of capabilities + per-project briefs + total open bugs |
| `mnemosyne_generate_feature_document` | grounded Markdown write-up of a project's features/capabilities |
| `mnemosyne_list_repositories_with_openspec` | org repositories that have OpenSpec (per latest sync) |
| `mnemosyne_list_repositories_missing_openspec` | org repositories missing OpenSpec (adoption targets) |
| `mnemosyne_get_repository_readiness` | observable readiness gate (MVP/READY/DONE) + per-check met/missing/unknown breakdown |
| `mnemosyne_get_organization_readiness` | org gate distribution + per-repo gate and missing-for-READY checks |
| `mnemosyne_get_readiness_history` | a repository's dated readiness-gate trend (recorded daily) |
| `mnemosyne_get_readiness_regressions` | org repos whose latest gate dropped below the previous (from/to gate + date) |
| `mnemosyne_remember` | persist a durable memory (note/decision/gotcha/convention/todo) scoped to a repo or org — **the one write tool**; writes to Mnemosyne, never GitHub |
| `mnemosyne_recall` | recall a repo's or org's memories, newest first, optional query/kind filter |
| `mnemosyne_forget` | delete a memory by id |

## Error contract

Tools return structured errors so agents can branch:

```json
{"error": {"code": "repository_not_synced", "message": "…"}}
```

Codes: `unknown_repository`, `repository_not_synced`, `mode_excludes_content`
(returned by code tools when a repo isn't indexed in a code mode),
`content_unavailable` (quarantined/uncaptured file), `not_found`,
`application_error`. Authentication failures raise MCP tool
errors prefixed `unauthenticated:` / `missing_entitlement:` /
`auth_unavailable:`.

## Recommended agent flow

1. `mnemosyne_build_context_pack(full_name, task)` before starting work —
   read `risks` and `suggested_next_steps`.
2. Fetch full content for the referenced items (`mnemosyne_get_readme`,
   `mnemosyne_get_issue`, …).
3. Use `mnemosyne_answer_from_repo_context` for point questions; it refuses
   (grounded=false) instead of fabricating when the index lacks coverage.
