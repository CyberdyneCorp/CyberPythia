# Proposal: add-code-context-indexing

## Why

Mnemosyne currently indexes documentation, OpenSpec, issues, PRs, file trees, and manifests — but not source-code *content*. Agents can see that `src/backend/gpu/cuda_backend.cpp` exists, but can't read it, search it semantically, or get the function that implements a behavior. Phase 3 closes this gap: it captures authorized source content, chunks it by symbol (functions, classes, modules), embeds those chunks for semantic **code** search, and surfaces them through REST and MCP — so an agent asked to "implement the OpenCL backend" gets the actual CUDA backend code to pattern-match against, not just its path.

Source code is the most sensitive content Mnemosyne touches, so this is opt-in per repository (the `code_context` / `full_context` indexing modes) and runs through the same `.mnemosyneignore`, path-denylist, and secret-scanning controls that already gate documentation.

## What Changes

- Two new indexing modes activate source-content capture:
  - `code_context` — file tree + selected source chunks + semantic code search index (documentation still captured; issues/PRs captured as in `project_intelligence`).
  - `full_context` — everything: docs, OpenSpec, issues, PRs, file tree, **and** source chunks.
- New `SourceFile` **content** capture and a `SourceChunk` entity (already sketched in the original domain spec, deferred until now): symbol-aware chunks with type, symbol name, line span, content, content hash, and embedding linkage.
- A **code chunker** domain service that splits a source file into symbol-bounded chunks (functions/classes/methods/modules) for the primary languages, with a windowed fallback for unsupported languages. Pure Python, behind a `CodeChunkerPort` so a tree-sitter-backed implementation can replace it later.
- Source chunks are embedded into pgvector (separate vector space / filter from doc chunks) via the existing `EmbeddingPort`, after secret scanning; chunks containing detected secrets are skipped, never embedded.
- New sync step `SOURCE_CODE` in the sync pipeline, run only for `code_context`/`full_context`, honoring ignore rules, secret quarantine, binary/generated-file exclusion, and a per-file size cap.
- Semantic **code search** and **symbol lookup** use cases; context packs enriched with `source_chunks` when the mode includes code.
- REST endpoints: `GET /repos/{id}/files/{file_id}/content`, `POST /repos/{id}/code-search`, `GET /repos/{id}/symbols`.
- MCP tools: `mnemosyne_get_file_content`, `mnemosyne_search_code`, `mnemosyne_get_symbol_context`, `mnemosyne_get_related_files`, `mnemosyne_explain_repository_structure`.
- Web UI **Code Context** tab: semantic code search box, symbol results with file/line links, on-demand file content viewer with syntax-aware display.
- Alembic migration adding the `source_chunks` table (+ pgvector column, repository/file/symbol indexes) and source-content columns on `source_files`.

### Non-goals (future changes)

- AST-accurate parsing via tree-sitter (the heuristic chunker is the v1; the port makes this swappable without a spec change).
- Cross-file call-graph / dependency-graph analysis beyond simple import-based "related files".
- Indexing whole binary/generated/vendored trees (excluded by policy).
- GitHub App / webhooks / incremental code re-sync (Phase 4).

## Capabilities

### New Capabilities

- `code-context`: Source-content capture, symbol-aware chunking, semantic code search, symbol lookup, and related-file discovery — gated by `code_context`/`full_context` modes and the security controls.

### Modified Capabilities

None (additive). Deltas add new requirements to existing capabilities without changing their current behavior:

- `repository-sync`: ADDED — source-code capture step for the new modes.
- `context-packs`: ADDED — include relevant source chunks when the mode captures code.
- `rest-api`: ADDED — file-content, code-search, and symbols endpoints.
- `mcp-interface`: ADDED — the five code tools.
- `web-ui`: ADDED — Code Context tab.

## Impact

- **Data model**: new `source_chunks` table + pgvector column; new content/columns on `source_files`; one Alembic migration.
- **Code**: new domain entity (`SourceChunk`), value object (`chunk_type`), domain service (`code_chunker`), port (`CodeChunkerPort`), use cases (code search, symbol lookup, file content), sync step, REST router additions, MCP tools, web Code Context tab.
- **Dependencies**: none new required (heuristic chunker is stdlib). `tree-sitter-language-pack` noted as an optional future adapter.
- **Cost/latency**: embedding source chunks increases OpenAI embedding volume and sync time for `code_context`/`full_context` repos; bounded by per-file size cap, ignore rules, and binary/generated exclusion. Existing repos default to `docs_only`/`project_intelligence`/`code_metadata` and are unaffected until an admin opts a repo into a code mode.
- **Security**: expands what can be embedded to source content; mitigated by opt-in modes, `.mnemosyneignore` + denylist, mandatory secret scanning before embedding, and audit logging of code-content access. No full source is sent to an LLM except the retrieved chunks a caller explicitly searches for.
