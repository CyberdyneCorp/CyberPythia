# Tasks: add-code-context-indexing

> Builds on the shipped core change. Reuse existing patterns (hexagonal layering, sync-step machinery, embedding store, router/error-model, MCP `_resolve_repo` + structured errors, Svelte detail tabs). Keep the domain pure; unit coverage > 90%.

## 1. Domain: modes, entity, chunker

- [x] 1.1 Add `full_context` to `IndexingMode`; add `includes_source_code` (true for `code_context`/`full_context`); make `code_context` include issues/PRs. Unit tests for the mode matrix.
- [x] 1.2 Add `SyncStep.SOURCE_CODE`; `SyncJob.steps_for_mode` inserts it after `FILE_TREE`, before `EMBEDDINGS`, only for code modes. Unit tests.
- [x] 1.3 `SourceChunk` entity (`chunk_type`, `symbol_name`, `start_line`, `end_line`, `content`, `content_hash`, `embedded`) + `ChunkType` value object (`function`, `method`, `class`, `interface`, `struct`, `module`, `window`). Add content-capture fields to `SourceFile` (`content_captured`, `content_hash`, `quarantined`). Unit tests.
- [x] 1.4 `CodeChunkerPort` + pure-Python `code_chunker` domain service: brace-language symbol chunking (C/C++/Java/Go/TS/JS/Solidity/Rust), Python indentation chunking, windowed fallback, oversized-body sub-splitting, deterministic hashing. Thorough unit tests per language + fallback + determinism.

## 2. Persistence

- [x] 2.1 SQLAlchemy `SourceChunkRow` (+ pgvector column) and new `source_files` columns; `SourceChunkPort`; Alembic migration `0002` (table, columns, repo/file/symbol indexes). Verify migration on real Postgres.
- [x] 2.2 Postgres `SourceChunkPort` adapter (replace-by-file, list-by-repository, get-by-symbol, delete-by-file) + integration tests.
- [x] 2.3 Extend file repository to persist/read `content`, `content_captured`, `content_hash`, `quarantined`; integration tests.

## 3. Embeddings & retrieval

- [x] 3.1 Extend embedding store: `embed_source_file(file_id, repository_id, chunks)` writing to `source_chunks`, and `search_code(repository_id, query, limit)` querying only source chunks; degraded-mode fallback parity. Integration tests (fake OpenAI).
- [x] 3.2 Code search use case + symbol lookup use case + file-content use case (mode/quarantine/notfound guards, audit on content read). Unit tests with fakes.
- [x] 3.3 Related-files use case (import/reference heuristic over captured content, both directions). Unit tests.

## 4. Sync pipeline

- [x] 4.1 `_sync_source_code` step in the orchestrator: fetch content for tree files (mode-gated), apply ignore/denylist + size cap + binary/generated exclusion, secret-scan → quarantine, chunk via port, persist chunks, mark files captured; content-hash skip on re-sync. Wire into the handler map.
- [x] 4.2 Unit tests for the step: captures for code modes, skipped for lower modes, ignore/oversize/binary exclusion, secret quarantine (no chunks/embeds), re-sync skip on unchanged hash, replace on changed hash. Extend the end-to-end integration sync test with a `code_context` fixture repo.

## 5. Context packs

- [x] 5.1 Include `source_chunks` in `build_context_pack` for code modes (via `search_code`); add `source_code` to excluded categories otherwise. Persist/serialize in the ContextPack entity + cache. Unit tests for code-mode and non-code-mode packs.

## 6. REST API

- [x] 6.1 Endpoints: `GET /repos/{id}/files/{file_id}/content`, `POST /repos/{id}/code-search`, `GET /repos/{id}/symbols`, `GET /repos/{id}/files/{file_id}/related`; schemas; 409 for non-code repos; audit on content read; OpenAPI security.
- [x] 6.2 Interface tests (auth matrix + mode gating + not-indexed 409 + content of quarantined/missing file).

## 7. MCP tools

- [x] 7.1 `mnemosyne_get_file_content`, `mnemosyne_search_code`, `mnemosyne_get_symbol_context`, `mnemosyne_get_related_files`, `mnemosyne_explain_repository_structure` with `mode_excludes_content` / `repository_not_synced` structured errors.
- [x] 7.2 MCP interface tests (tool listing includes the code tools; happy path on a seeded code-mode repo; mode/unsynced errors).

## 8. Web UI

- [x] 8.1 Code Context tab: semantic code-search box, ranked symbol results (path/symbol/type/line span/excerpt) with file+line links, on-demand content viewer; not-indexed message for non-code repos. New API client methods + viewmodel.
- [x] 8.2 Viewmodel unit tests; extend the populated-dashboard Playwright spec to cover code search on a `code_context` pilot repo.

## 9. Docs, deploy, verification

- [x] 9.1 Update README + docs (indexing modes table incl. `code_context`/`full_context`, code MCP tools in `docs/mcp-consumers.md`, security note on source capture). New env: source size cap, window size/overlap.
- [ ] 9.2 Run full gate (ruff, mypy --strict, unit coverage ≥ 90%, integration, BDD) + `openspec validate --all --strict`; deploy `0002` migration + code; set a pilot repo to `code_context`, re-sync, verify real code search/symbol/content over REST + MCP + UI.
