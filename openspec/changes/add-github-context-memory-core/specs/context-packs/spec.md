# context-packs — task-specific context for agents and repository Q&A

## ADDED Requirements

### Requirement: Document embeddings for semantic search
The system SHALL embed captured documents (chunked at document/section level) into pgvector using a configurable embedding model, and SHALL support semantic search over a repository's documents. Quarantined or ignored content SHALL never be embedded.

#### Scenario: Semantic doc search
- **WHEN** a caller searches a synced repository for "how is authentication implemented"
- **THEN** the system SHALL return the most relevant documents ranked by semantic similarity with paths and excerpts

### Requirement: Build a context pack
The system SHALL build a context pack for a (repository, task query) pair containing: a repository summary, relevant documents, relevant OpenSpec changes, relevant issues, relevant pull requests, relevant file paths (when file tree is captured), identified risks, and suggested next steps. Relevance SHALL combine semantic search over documents with keyword/label matching over issues, PRs, and OpenSpec changes. The pack SHALL respect the repository's indexing mode — it SHALL never include content categories the mode excludes.

#### Scenario: Context pack for a task
- **WHEN** an entitled caller requests a context pack for repository R with query "implement OpenCL backend"
- **THEN** the response SHALL include ranked relevant docs, OpenSpec changes, issues, and PRs, each with identifiers/paths usable to fetch full content

#### Scenario: Mode-constrained pack
- **WHEN** a context pack is requested for a `docs_only` repository
- **THEN** the pack SHALL contain documentation and OpenSpec context only, and SHALL state that issues/PRs are not indexed

#### Scenario: Unsynced repository
- **WHEN** a context pack is requested for a repository that has never completed a sync
- **THEN** the system SHALL return an error indicating the repository must be synced first

### Requirement: Context pack persistence and caching
The system SHALL persist built context packs with their inputs (repository, query, mode) and creation time, and SHALL serve a cached pack for an identical (repository, query, mode) tuple while the underlying sync timestamp is unchanged.

#### Scenario: Repeated identical request
- **WHEN** the same caller or another caller requests an identical context pack before any new sync
- **THEN** the cached pack SHALL be returned without recomputation

### Requirement: Ask a repository question
The system SHALL answer natural-language questions about a synced repository using only indexed content, returning the answer together with source references (document paths, issue/PR numbers, OpenSpec change ids). When indexed content is insufficient the system SHALL say so rather than fabricate.

#### Scenario: Answer with citations
- **WHEN** an entitled caller asks "what is the deployment process?" for a repository with deployment docs
- **THEN** the answer SHALL cite the documents it derives from

#### Scenario: Insufficient context
- **WHEN** the question cannot be grounded in indexed content
- **THEN** the response SHALL state that the indexed context does not cover the question and list what content types are indexed
