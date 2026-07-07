# repository-sync — source-code capture step

## ADDED Requirements

### Requirement: Source-code sync step
The sync pipeline SHALL include a `source_code` step that runs only for repositories indexed as `code_context` or `full_context`, after the file-tree step and before embeddings. The step SHALL capture authorized source content, chunk it, and persist chunks, recording its own per-step status and item count like every other step. Its failure SHALL fail the job without discarding data from steps that succeeded.

#### Scenario: Step runs for code modes
- **WHEN** a `code_context` or `full_context` sync is planned
- **THEN** the planned steps SHALL include `source_code` positioned after `file_tree` and before `embeddings`

#### Scenario: Step skipped for lower modes
- **WHEN** a `docs_only`, `project_intelligence`, or `code_metadata` sync is planned
- **THEN** the planned steps SHALL NOT include `source_code`

#### Scenario: Step failure recorded
- **WHEN** the source-code step fails partway through a sync
- **THEN** the step SHALL be marked failed, the job SHALL be marked failed, and successfully captured chunks and other steps' data SHALL be retained
