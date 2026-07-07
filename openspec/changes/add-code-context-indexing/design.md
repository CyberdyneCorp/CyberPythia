# Design: add-code-context-indexing

## Context

Builds on the shipped `add-github-context-memory-core` change (deployed, verified with real data). That change already captures the file tree and detects languages/manifests in `code_metadata` mode, and defined a `SourceChunk` entity shape in the domain spec that was deliberately not implemented. Phase 3 implements source-content capture and semantic code search on top of the existing hexagonal backend, pgvector store, sync pipeline, REST API, MCP server, and Svelte UI.

Constraints unchanged: hexagonal (pure domain), `uv`/`just`, unit coverage > 90%, security-critical (source is the most sensitive content), no native deps in the default build.

## Goals / Non-Goals

**Goals**
- Opt-in source capture via `code_context` / `full_context` modes, reusing every existing security control.
- Symbol-aware, deterministic, pure-Python chunking behind a swappable port.
- Semantic code search distinct from doc search, plus symbol lookup and related files.
- Code surfaces on REST, MCP, and the web UI; source chunks in context packs.

**Non-Goals**
- AST-perfect parsing (heuristic v1; tree-sitter is a future adapter).
- Call-graph/dependency analysis beyond import-based related files.
- Incremental/webhook code re-sync (Phase 4).

## Decisions

### D1. Two cumulative modes; one new sync step
`IndexingMode` gains `full_context`. Capture rules by mode:
- `code_metadata` — tree + manifests (unchanged).
- `code_context` — tree + **source chunks** + docs + issues/PRs (superset of `project_intelligence` for non-code categories).
- `full_context` — everything.

`SyncStep.SOURCE_CODE` is inserted after `FILE_TREE`, before `EMBEDDINGS`, and `SyncJob.steps_for_mode` includes it only for the two code modes. This keeps the orchestrator's per-step status/idempotency/lock machinery unchanged.

### D2. Heuristic chunker behind `CodeChunkerPort` (pure Python, no native deps)
A domain service `code_chunker` splits source by symbol using per-language lightweight rules:
- Brace languages (C/C++, Java, Go, TS/JS, Solidity, Rust): detect top-level and nested `func`/`function`/`class`/`interface`/`struct`/`impl` declarations by signature regex, then bound each chunk by brace balance.
- Indentation languages (Python): detect `def`/`class` at a given indent, bound by dedent.
- Everything else: fixed line-window chunks (default 80 lines, 10-line overlap), `chunk_type = window`.
Deterministic (no `Date`/random). Oversized symbol bodies are sub-split by the window rule so no chunk exceeds the embedding size cap.
- *Why heuristic, not tree-sitter*: tree-sitter needs native wheels that complicate the Coolify build and add per-language grammars; the heuristic is good enough for retrieval (we embed the chunk text regardless of perfect boundaries) and the `CodeChunkerPort` lets a tree-sitter adapter drop in later with no spec change. Recorded as the deliberate v1 trade-off.

### D3. `SourceChunk` entity + table; content on `source_files`
New `source_chunks` table: `id, file_id, repository_id, chunk_type, symbol_name, start_line, end_line, content, content_hash, embedded (bool)`. `source_files` gains `content_captured (bool)`, `content_hash`, `quarantined (bool)`. Alembic migration `0002` adds these. Doc chunks already live in `document_chunks` with a pgvector column; source chunks get their own table so code and doc search never bleed into each other and can be filtered/scaled independently.

### D4. Embeddings: reuse `EmbeddingPort`, separate corpus
Extend the embedding store with `embed_source_file(file_id, repository_id, chunks)` and `search_code(repository_id, query, limit)` querying `source_chunks` only. Same OpenAI model and degraded-mode fallback as docs. Secret scanning runs in the sync step *before* the port is called; quarantined files never reach it.

### D5. Retrieval-only exposure to the LLM
Code search and symbol lookup return chunks; the LLM only ever receives the specific chunks a caller's query retrieved (as with `ask`). No endpoint streams a whole repository to a model. File-content retrieval is a direct DB read of already-captured content, audit-logged.

### D6. Related files: import heuristic over captured metadata
`get_related_files` scans a file's captured content for import/include/require statements, resolves them best-effort to other captured file paths in the same repo, and also returns files that import the target. No persistent graph in v1 — computed on demand from stored content, bounded by repo size.

### D7. Reuse existing interface patterns
REST additions follow the current router/mapping/error-model conventions; MCP tools follow the `_resolve_repo` + structured-error pattern (adding a `mode_excludes_content` branch for non-code repos); the web Code Context tab reuses the search/viewer components. No new cross-cutting infrastructure.

## Risks / Trade-offs

- [Heuristic chunker mis-bounds exotic syntax] → chunks still embed usable text; retrieval degrades gracefully, and the port allows a tree-sitter upgrade. Windowed fallback guarantees coverage.
- [Embedding cost/time on large code repos] → per-file size cap, binary/generated/ignore exclusion, content-hash skip on re-sync, and opt-in modes bound the volume; log counts of captured vs skipped files.
- [Secret leakage via source chunks] → mandatory secret scan before chunk persistence/embedding (same scanner as docs), quarantine with audit; `.mnemosyneignore` + denylist enforced in the same choke point as docs.
- [Sensitive-repo exposure] → source capture is off unless an admin sets a code mode; file-content access is entitled + audited.
- [Coverage floor with a new I/O-light but branchy chunker] → the chunker is pure and gets thorough unit tests (per-language symbol cases + fallback + determinism); adapters/integration stay outside the unit-coverage scope.

## Migration Plan

Additive, backward-compatible. Deploy order:
1. Alembic `0002` (new table + columns) — safe on the running DB (no backfill; existing repos have no source content).
2. Deploy backend/mcp/worker/web with the new code.
3. An admin sets a pilot repo to `code_context`/`full_context` and re-syncs; the new step captures + embeds source.
Rollback: revert images; `alembic downgrade` drops the new table/columns (pre-GA only). Repos left in lower modes are unaffected throughout.

## Open Questions

- OQ1: Per-file size cap default — 512 KB assumed; confirm against real repo distributions during the pilot.
- OQ2: Windowed-chunk size/overlap defaults (80/10 lines) — tune against retrieval quality on the pilot repos.
- OQ3: Whether to also embed a per-file summary chunk for "explain structure" (deferred; `explain_repository_structure` can derive from tree + symbols without it initially).
