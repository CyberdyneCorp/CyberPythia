# repository-sync Specification

## MODIFIED Requirements

### Requirement: Sync orchestration
The system SHALL run repository syncs as asynchronous jobs on a Redis-backed queue processed by a worker service. A sync SHALL be idempotent, SHALL hold a per-repository lock preventing concurrent syncs of the same repository, SHALL record per-step progress and status (`pending`, `running`, `succeeded`, `failed`), and SHALL respect GitHub rate limits with backoff.

Steps SHALL be classified as **essential** (metadata, docs, OpenSpec, issues, pull requests, file tree, metrics) or **best-effort** (source code, embeddings). The job outcome SHALL be `succeeded` when all steps succeed, `failed` when any essential step fails, and `degraded` when only best-effort steps fail. The repository's `last_synced_at` SHALL advance whenever all essential steps succeed (i.e. for both `succeeded` and `degraded` jobs), so an enrichment failure does not leave a repository looking un-synced. Failed steps SHALL be recorded per-step in every case.

#### Scenario: Concurrent sync requests
- **WHEN** a sync is triggered for a repository that already has a running sync
- **THEN** the second request SHALL be rejected or coalesced, and only one sync SHALL run

#### Scenario: Essential step failure fails the job
- **WHEN** an essential step (e.g. issues fetch) fails after other steps succeeded
- **THEN** the job SHALL record the failed step, the status SHALL be `failed`, `last_synced_at` SHALL NOT advance, and successful steps' data SHALL be retained

#### Scenario: Best-effort step failure degrades the job
- **WHEN** only best-effort steps (source code and/or embeddings) fail and all essential steps succeed
- **THEN** the status SHALL be `degraded`, `last_synced_at` SHALL advance, and the failed steps SHALL be recorded

#### Scenario: Rate limit reached
- **WHEN** GitHub returns rate-limit exhaustion during a sync
- **THEN** the worker SHALL pause and resume after the reset time rather than failing the job

### Requirement: Source-code sync step
The sync pipeline SHALL include a `source_code` step that runs only for repositories indexed as `code_context` or `full_context`, after the file-tree step and before embeddings. The step SHALL capture authorized source content, chunk it, and persist chunks, recording its own per-step status and item count like every other step. As a best-effort step, its failure SHALL degrade the job (not fail it) without discarding data from steps that succeeded.

#### Scenario: Step runs for code modes
- **WHEN** a `code_context` or `full_context` sync is planned
- **THEN** the planned steps SHALL include `source_code` positioned after `file_tree` and before `embeddings`

#### Scenario: Step skipped for lower modes
- **WHEN** a `docs_only`, `project_intelligence`, or `code_metadata` sync is planned
- **THEN** the planned steps SHALL NOT include `source_code`

#### Scenario: Step failure recorded
- **WHEN** the source-code step fails partway through a sync
- **THEN** the step SHALL be marked failed, the job SHALL be marked `degraded` (essential steps unaffected), and successfully captured chunks and other steps' data SHALL be retained
