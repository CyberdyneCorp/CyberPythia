# MCP consumer guide

The MCP server (`mnemosyne-mcp`, streamable HTTP at `/mcp`) exposes the
Mnemosyne tool suite to agents. Every call requires a CyberdyneAuth bearer
token with the `mnemosyne` entitlement.

## Connecting

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

transport = StreamableHttpTransport("https://mnemosyne-mcp.<domain>/mcp", auth=TOKEN)
async with Client(transport) as client:
    repos = await client.call_tool("mnemosyne_list_repositories", {})
```

Claude Code: `claude mcp add --transport http mnemosyne https://mnemosyne-mcp.<domain>/mcp --header "Authorization: Bearer <token>"`.

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
