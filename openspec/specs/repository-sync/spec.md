# repository-sync Specification

## Purpose
TBD - created by archiving change add-github-context-memory-core. Update Purpose after archive.
## Requirements
### Requirement: Repository discovery
The system SHALL discover repositories available to a registered GitHub credential (user and organization repositories) and persist their metadata: GitHub id, owner, name, full name, description, visibility, default branch, primary language, archived status, and last update timestamp.

#### Scenario: Discovery after connection
- **WHEN** an admin runs discovery on a valid connection
- **THEN** the system SHALL list all accessible repositories with their metadata, without indexing any content

### Requirement: Repository selection for indexing
The system SHALL index only repositories explicitly enabled by an admin (allowlist). Each enabled repository SHALL have an indexing mode of `docs_only` or `project_intelligence` or `code_metadata`; content capture SHALL never exceed the selected mode.

#### Scenario: Repository not selected
- **WHEN** a discovered repository has not been enabled
- **THEN** no sync job SHALL run for it and no content SHALL be fetched beyond discovery metadata

#### Scenario: Mode limits capture
- **WHEN** a repository is enabled with mode `docs_only`
- **THEN** the sync SHALL capture documentation and OpenSpec content only — no issues, PRs, or file tree

### Requirement: Sync orchestration
The system SHALL run repository syncs as asynchronous jobs on a Redis-backed queue processed by a worker service. A sync SHALL be idempotent, SHALL hold a per-repository lock preventing concurrent syncs of the same repository, SHALL record per-step progress and status (`pending`, `running`, `succeeded`, `failed`), and SHALL respect GitHub rate limits with backoff.

#### Scenario: Concurrent sync requests
- **WHEN** a sync is triggered for a repository that already has a running sync
- **THEN** the second request SHALL be rejected or coalesced, and only one sync SHALL run

#### Scenario: Partial failure
- **WHEN** a sync step fails (e.g., issues fetch) after other steps succeeded
- **THEN** the job SHALL record the failed step and the sync status SHALL be `failed` with successful steps' data retained

#### Scenario: Rate limit reached
- **WHEN** GitHub returns rate-limit exhaustion during a sync
- **THEN** the worker SHALL pause and resume after the reset time rather than failing the job

### Requirement: Documentation capture and classification
The system SHALL capture documentation files from enabled repositories — `README*`, `docs/**/*.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `SECURITY.md`, `CHANGELOG.md`, `ROADMAP.md`, and markdown under documentation folders — and classify each as one of: `README`, `DOCS`, `OPENSPEC`, `ARCHITECTURE`, `SECURITY`, `CHANGELOG`, `CONTRIBUTING`, `ROADMAP`, `GENERIC_MARKDOWN`. Each document SHALL store path, title, content, content hash, and last commit SHA, and SHALL be updated only when the content hash changes.

#### Scenario: README captured
- **WHEN** a sync runs on a repository with a root `README.md`
- **THEN** a document of type `README` SHALL be persisted with its content and commit SHA

#### Scenario: Unchanged document on re-sync
- **WHEN** a re-sync finds a document whose content hash matches the stored one
- **THEN** the system SHALL NOT rewrite the document or re-embed it

### Requirement: OpenSpec capture
The system SHALL detect OpenSpec content in conventional locations (`openspec/`, `specs/`, `changes/`) and persist each OpenSpec change with: change id, proposal content, design content, tasks content, affected specs, inferred status (active or archived), and paths.

#### Scenario: Repository with OpenSpec changes
- **WHEN** a sync runs on a repository containing `openspec/changes/<id>/proposal.md`
- **THEN** an OpenSpec change record SHALL be persisted with its proposal, and its tasks/design when present

### Requirement: Issues capture
The system SHALL capture issues for enabled repositories (mode `project_intelligence` or higher) including number, title, body, state, author, labels, assignees, milestone, created/closed dates, comment count, and computed resolution time for closed issues. Pull requests SHALL NOT be stored as issues.

#### Scenario: Closed issue resolution time
- **WHEN** a closed issue is synced
- **THEN** its resolution time SHALL equal closed_at minus created_at

### Requirement: Pull request capture
The system SHALL capture pull requests for enabled repositories (mode `project_intelligence` or higher) including number, title, body, state, merged flag, author, reviewers, created/closed/merged dates, changed files count, additions, deletions, review decision, first review timestamp, and computed time-to-merge and time-to-first-review.

#### Scenario: Merged PR metrics fields
- **WHEN** a merged PR is synced
- **THEN** time-to-merge SHALL equal merged_at minus created_at, and time-to-first-review SHALL be set when at least one review exists

### Requirement: File tree capture
The system SHALL capture the default-branch file tree for enabled repositories (mode `code_metadata`) including path, extension, detected language, size, blob SHA, and binary flag, and SHALL flag important files (dependency manifests, Dockerfiles, CI workflows, IaC, OpenAPI specs). File content SHALL NOT be captured in this change.

#### Scenario: Manifest detection
- **WHEN** a file tree containing `pyproject.toml` is synced
- **THEN** the file SHALL be flagged as an important dependency manifest

### Requirement: Raw payload snapshots
The system SHALL store raw GitHub API payloads (repository metadata, issues pages, PR pages, trees) in object storage (MinIO) keyed by repository and sync, for auditability and reprocessing.

#### Scenario: Sync stores raw payloads
- **WHEN** any sync step fetches GitHub data
- **THEN** the raw response payload SHALL be persisted to object storage before normalization

### Requirement: Ignore rules before indexing
The system SHALL honor a `.mnemosyneignore` file at the repository root and a global path denylist: matching paths SHALL be excluded from documentation capture, file-tree records, and embeddings. The system SHALL run secret scanning on captured document content before persistence or embedding and SHALL quarantine (persist metadata only, flag, and exclude content) documents containing detected secrets.

#### Scenario: Ignored path
- **WHEN** a repository's `.mnemosyneignore` matches `internal/legal/`
- **THEN** no document or file record under that path SHALL be captured

#### Scenario: Secret detected in a document
- **WHEN** secret scanning flags captured content
- **THEN** the content SHALL NOT be stored or embedded, and the document SHALL be marked quarantined

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

### Requirement: Incremental issue sync
The system SHALL support fetching and upserting a single issue by number for an enabled repository, without running a full repository sync. The upsert SHALL apply the same normalization and exclusions as the batch issue sync (pull requests are never stored as issues). After the upsert the repository's issue metrics SHALL be recomputed.

#### Scenario: Upsert one issue
- **WHEN** an incremental issue sync runs for issue #42 on an enabled repository
- **THEN** only issue #42 SHALL be fetched and upserted, and issue metrics SHALL be recomputed

#### Scenario: Incremental issue on a disabled repository
- **WHEN** an incremental issue sync is requested for a repository not enabled for indexing
- **THEN** no fetch or upsert SHALL occur

### Requirement: Incremental pull-request sync
The system SHALL support fetching and upserting a single pull request by number for an enabled repository, without a full sync, applying the same fields and derived timings as the batch PR sync, then recomputing PR metrics.

#### Scenario: Upsert one pull request
- **WHEN** an incremental PR sync runs for PR #61 on an enabled repository
- **THEN** only PR #61 SHALL be fetched and upserted, and PR metrics SHALL be recomputed

### Requirement: Milestone capture
The system SHALL capture a repository's GitHub milestones as records including title, state,
due date (when set), and open/closed issue counts, and SHALL keep them in sync on each
repository sync. Issues already carry their milestone name; milestone progress joins on it.

#### Scenario: Milestones captured on sync
- **GIVEN** a repository with milestones on GitHub
- **WHEN** the repository is synced
- **THEN** each milestone SHALL be stored with its state, due date, and issue counts

#### Scenario: Milestone without a due date
- **GIVEN** a milestone with no due date
- **WHEN** it is captured
- **THEN** it SHALL be stored with a null due date and still counted for progress

### Requirement: Issue first-response capture
The system SHALL capture, where determinable, the timestamp of the first non-author response
on an issue, stored as a nullable field. When it cannot be determined, the field SHALL remain
null and downstream metrics SHALL treat it as insufficient data.

#### Scenario: First response recorded
- **GIVEN** an issue with a comment from someone other than its author
- **WHEN** the repository is synced
- **THEN** the issue's first-response timestamp SHALL be recorded

### Requirement: Issue reopened count capture
The system SHALL capture how many times an issue has been reopened, stored as a count that
defaults to zero.

#### Scenario: Reopened issue counted
- **GIVEN** an issue that was closed and reopened
- **WHEN** the repository is synced
- **THEN** the issue's reopened count SHALL reflect the reopen

