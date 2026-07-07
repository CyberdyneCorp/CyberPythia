# code-context — source-content capture, chunking, and semantic code search

## ADDED Requirements

### Requirement: Source-content capture is opt-in per repository
The system SHALL capture source-file content only for repositories whose indexing mode is `code_context` or `full_context`. For any lower mode the system SHALL NOT fetch, store, chunk, or embed source content.

#### Scenario: Mode below code_context
- **WHEN** a repository indexed as `code_metadata` (or lower) is synced
- **THEN** file-tree metadata SHALL be captured but no source content, chunks, or code embeddings SHALL be produced

#### Scenario: code_context mode
- **WHEN** a repository indexed as `code_context` is synced
- **THEN** authorized source files SHALL have their content captured, chunked, and embedded

### Requirement: Source capture honors security controls
Source-content capture SHALL exclude any path matched by `.mnemosyneignore` or the global denylist, SHALL exclude binary and generated files, and SHALL skip files larger than a configurable size cap (default 512 KB). Every captured source file SHALL be secret-scanned before chunking; a file with detected secrets SHALL be quarantined (metadata retained, content and chunks excluded) and SHALL NOT be embedded.

#### Scenario: Ignored source path
- **WHEN** a source path matches the denylist or `.mnemosyneignore`
- **THEN** its content SHALL NOT be captured or chunked

#### Scenario: Oversized file
- **WHEN** a source file exceeds the size cap
- **THEN** the file SHALL be recorded in the tree but its content SHALL NOT be captured

#### Scenario: Secret in a source file
- **WHEN** secret scanning flags a source file's content
- **THEN** no chunk of that file SHALL be stored or embedded, and the file SHALL be marked quarantined

### Requirement: Symbol-aware code chunking
The system SHALL split captured source content into chunks bounded by code symbols (functions, methods, classes, interfaces, or module-level regions) for supported languages, recording for each chunk: chunk type, symbol name (when identifiable), start line, end line, content, and content hash. For unsupported languages the system SHALL fall back to fixed-size line-window chunks. Chunking SHALL be deterministic for a given file content.

#### Scenario: Function-bounded chunk
- **WHEN** a supported-language file defining a function `dispatch_kernels` is chunked
- **THEN** a chunk of type `function` with symbol name `dispatch_kernels` and its line span SHALL be produced

#### Scenario: Unsupported language fallback
- **WHEN** a file in an unsupported language is chunked
- **THEN** it SHALL be split into windowed chunks of type `window` with line spans and no symbol name

#### Scenario: Determinism
- **WHEN** the same file content is chunked twice
- **THEN** the chunk boundaries, types, and hashes SHALL be identical

### Requirement: Source chunks are embedded and re-indexed on change
Non-quarantined source chunks SHALL be embedded into the vector store, tagged so code chunks are distinguishable from documentation chunks. On re-sync, a source file whose content hash is unchanged SHALL NOT be re-chunked or re-embedded; a changed file SHALL have its prior chunks replaced.

#### Scenario: Unchanged file on re-sync
- **WHEN** a re-sync encounters a source file whose content hash matches the stored value
- **THEN** its chunks SHALL NOT be re-embedded

#### Scenario: Changed file on re-sync
- **WHEN** a source file's content hash changes
- **THEN** its previous chunks SHALL be deleted and the new content re-chunked and re-embedded

### Requirement: Semantic code search
The system SHALL provide semantic search over a repository's source chunks, returning ranked matches with file path, symbol name, chunk type, line span, an excerpt, and a similarity score. Code search SHALL only return chunks from repositories indexed in a code mode.

#### Scenario: Code search returns symbol matches
- **WHEN** an entitled caller searches a `code_context` repository for "dispatch GPU kernels"
- **THEN** the most relevant source chunks SHALL be returned ranked by similarity, each identifying its file and symbol

#### Scenario: Code search on a non-code repository
- **WHEN** code search is requested for a repository indexed below `code_context`
- **THEN** the system SHALL return an error indicating source code is not indexed for that repository

### Requirement: File content on demand
The system SHALL return the captured content of a specific source file by id for an entitled caller, or an error if the file was not content-captured (wrong mode, ignored, oversized, binary, or quarantined). Retrieving source content SHALL be audit-logged.

#### Scenario: Fetch captured file content
- **WHEN** an entitled caller requests the content of a captured source file
- **THEN** the file content SHALL be returned and the access SHALL be audit-logged

#### Scenario: Fetch content of a quarantined file
- **WHEN** a caller requests content of a quarantined or non-captured file
- **THEN** the system SHALL return an error stating the content is not available and why

### Requirement: Symbol lookup and related files
The system SHALL let a caller look up source chunks by symbol name within a repository, and SHALL surface files related to a given file via import/reference heuristics. Results SHALL respect the repository's indexing mode.

#### Scenario: Symbol lookup
- **WHEN** a caller looks up the symbol `dispatch_kernels` in a code-indexed repository
- **THEN** the chunk(s) defining that symbol SHALL be returned with file path and line span

#### Scenario: Related files
- **WHEN** a caller requests files related to `src/backend/gpu/cuda_backend.cpp`
- **THEN** the system SHALL return files it imports or that reference it, best-effort, from captured metadata
