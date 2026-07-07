# repository-sync — discovery, selection, and sync pipeline

## ADDED Requirements

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
