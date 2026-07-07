# context-packs — source chunks in packs

## ADDED Requirements

### Requirement: Context packs include relevant source chunks
When a context pack is built for a repository indexed in a code mode (`code_context` or `full_context`), the pack SHALL include a `source_chunks` section of the most relevant source chunks for the query — each with file path, symbol name, chunk type, line span, and score — obtained by semantic code search. For repositories not indexed for code, `source_chunks` SHALL be empty and `source_code` SHALL be listed among the pack's excluded categories.

#### Scenario: Code-mode pack includes source chunks
- **WHEN** a context pack is built for a `code_context` repository with a task query that matches captured code
- **THEN** the pack SHALL include ranked relevant source chunks with their file paths and symbols

#### Scenario: Non-code-mode pack excludes source chunks
- **WHEN** a context pack is built for a `project_intelligence` repository
- **THEN** `source_chunks` SHALL be empty and `source_code` SHALL appear in the pack's excluded categories
