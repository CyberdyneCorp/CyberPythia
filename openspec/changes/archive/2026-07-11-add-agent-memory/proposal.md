# Agent-writable memory

## Why

Mnemosyne is named for memory but today only *reads* GitHub — there is no way for
an agent (or human) to persist what it learns. A repo's non-obvious gotchas,
decisions, and conventions live only in a single agent's transcript and are lost.
The namesake capability is missing: durable, shared memory that later agents
recall alongside the indexed context.

## What changes

A small, first-class **memory store** scoped to a repository or an organization:

- **Write** — an entitled caller records a memory (free-text `content`, a `kind`
  such as note/decision/gotcha/convention/todo) scoped to a repo or an org. This
  is the first agent-facing *write* surface; it writes only to Mnemosyne's own
  store, never to GitHub.
- **Recall** — list a scope's memories, optionally filtered by `kind` and a text
  `query` (trigram/substring match), newest first.
- **Forget** — delete a memory by id.
- Deleting a repository or connection cascades its memories away.

Folding memories into context packs (so an agent building context sees prior
learnings automatically) is a deliberate fast-follow — it touches the cached
pack entity and is kept out of this change to stay focused.

## Impact

- Data model: new `agent_memories` table (migration `0009`; repo- or org-scoped).
- New capability spec `agent-memory`; deltas to context-packs, mcp-interface,
  rest-api, web-ui.
- MCP: `mnemosyne_remember`, `mnemosyne_recall`, `mnemosyne_forget`.
- REST: memory CRUD under `/repos/{id}/memories` + org-scoped list/create.
- Web: a Memory tab on the repository detail page.
