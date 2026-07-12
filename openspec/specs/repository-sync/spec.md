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
The system SHALL store raw GitHub API payloads (repository metadata, issues pages, PR pages, trees) in object storage (MinIO) keyed by repository and sync, for auditability and reprocessing. Object-storage keys SHALL be constrained to their intended prefix: a key containing a `..` path-traversal segment SHALL be rejected rather than written.

#### Scenario: Sync stores raw payloads
- **WHEN** any sync step fetches GitHub data
- **THEN** the raw response payload SHALL be persisted to object storage before normalization

#### Scenario: Traversing object key rejected
- **WHEN** a raw-snapshot key would contain a `..` traversal segment (e.g. from a malformed repository full name)
- **THEN** the write SHALL be rejected and no object SHALL be persisted outside the intended prefix

### Requirement: Ignore rules before indexing
The system SHALL honor a `.mnemosyneignore` file at the repository root and a global path denylist: matching paths SHALL be excluded from documentation capture, file-tree records, and embeddings. The system SHALL run secret scanning on captured document content before persistence or embedding and SHALL quarantine (persist metadata only, flag, and exclude content) documents containing detected secrets.

#### Scenario: Ignored path
- **WHEN** a repository's `.mnemosyneignore` matches `internal/legal/`
- **THEN** no document or file record under that path SHALL be captured

#### Scenario: Secret detected in a document
- **WHEN** secret scanning flags captured content
- **THEN** the content SHALL NOT be stored or embedded, and the document SHALL be marked quarantined

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

### Requirement: Scheduled daily full sync
The system SHALL run a scheduled job at least once per day that enqueues a full sync for every
enabled repository, using each repository's configured indexing mode. The job SHALL skip a
repository whose sync is already pending or running (never enqueuing a duplicate), and a failure
to enqueue one repository SHALL NOT prevent the others from being enqueued. The schedule SHALL be
configurable and SHALL be disableable.

To avoid starving repositories when the GitHub rate budget cannot cover the whole set in one run,
the job SHALL enqueue repositories **least-recently-synced first** (repositories never synced
before those with the oldest `last_synced_at`). The job MAY cap the number of repositories
enqueued per run via configuration (unbounded by default); when capped, the remaining
repositories are deferred to a later run and, because they remain least-recently-synced, are
prioritised then.

#### Scenario: Daily run enqueues all enabled repositories
- **WHEN** the scheduled sync runs
- **THEN** the system SHALL enqueue a sync for each enabled repository
- **AND** disabled repositories SHALL NOT be enqueued

#### Scenario: A repository already syncing is skipped
- **GIVEN** a repository whose sync is already pending or running
- **WHEN** the scheduled sync runs
- **THEN** that repository SHALL be skipped rather than enqueued again

#### Scenario: One repository failing does not stop the run
- **GIVEN** enqueuing one repository raises an error
- **WHEN** the scheduled sync runs
- **THEN** the remaining enabled repositories SHALL still be enqueued

#### Scenario: Least-recently-synced repositories are enqueued first
- **WHEN** the scheduled sync runs
- **THEN** repositories SHALL be enqueued ordered by `last_synced_at` ascending (never-synced first), so a repository that failed to sync previously is prioritised on the next run

#### Scenario: Per-run cap defers the remainder
- **GIVEN** a per-run cap smaller than the number of enabled repositories
- **WHEN** the scheduled sync runs
- **THEN** at most that many repositories SHALL be enqueued, the least-recently-synced ones, and the rest SHALL be deferred to a later run

### Requirement: Scheduled discovery with auto-enable of new repositories
The system SHALL, as part of the daily scheduled job, re-discover the repositories each
connection can access and auto-enable repositories that are **newly discovered** — a repository
whose GitHub id was not present before the run — provided the repository is not archived, using a
configured indexing mode. The system SHALL NOT change the enabled state of any repository that
already existed, so a repository an admin has disabled SHALL remain disabled. Discovery and
auto-enable SHALL run before the daily full sync so a new repository is discovered, enabled, and
synced in the same run. The behaviour SHALL be configurable and disableable.

#### Scenario: A newly-created repository is auto-enabled and synced
- **GIVEN** a repository that appears in discovery for the first time and is not archived
- **WHEN** the scheduled job runs
- **THEN** that repository SHALL be enabled in the configured mode
- **AND** it SHALL be included in the same run's full sync

#### Scenario: Manually disabled repositories are not re-enabled
- **GIVEN** a repository that already existed and was disabled by an admin
- **WHEN** the scheduled discovery runs and sees it again
- **THEN** its enabled state SHALL be left unchanged (it SHALL remain disabled)

#### Scenario: Archived repositories are skipped
- **GIVEN** a newly-discovered repository that is archived
- **WHEN** auto-enable runs
- **THEN** that repository SHALL NOT be enabled

#### Scenario: Auto-enable disabled by configuration
- **GIVEN** auto-enable is turned off by configuration
- **WHEN** the scheduled discovery runs
- **THEN** no repository SHALL be enabled, even if newly discovered

### Requirement: Staggered scheduled fan-out
When the scheduled job enqueues syncs for the enabled repositories, it SHALL spread the enqueues
over time by an increasing per-repository delay, rather than enqueuing them all at once, to smooth
the request rate against GitHub. The stagger interval SHALL be configurable.

#### Scenario: Enqueues are spread, not bursted
- **WHEN** the scheduled sync enqueues syncs for many enabled repositories
- **THEN** each successive repository's sync SHALL be deferred by a progressively larger delay

#### Scenario: All enabled repositories are still enqueued
- **WHEN** the scheduled sync runs with staggering enabled
- **THEN** every enabled repository SHALL still be enqueued (staggering delays, it does not drop any)

### Requirement: Bounded rate-limit wait with fail-fast
When a GitHub request is rate-limited, the system SHALL determine the wait until the limit resets
from `X-RateLimit-Reset` or `Retry-After`. If the wait is within a configurable maximum, the system
SHALL wait and retry; if the wait exceeds that maximum, the system SHALL fail the request with a
distinct rate-limit error rather than blocking, so the worker slot is freed and the affected
repository is retried on the next scheduled run.

#### Scenario: Short limit is absorbed
- **GIVEN** a rate-limited response whose reset is within the maximum wait
- **WHEN** the request is made
- **THEN** the system SHALL wait until reset and retry the request

#### Scenario: Long limit fails fast
- **GIVEN** a rate-limited response whose reset is beyond the maximum wait
- **WHEN** the request is made
- **THEN** the system SHALL raise a rate-limit error immediately without blocking for the full reset

#### Scenario: Secondary limit honours Retry-After
- **GIVEN** a rate-limited response carrying a `Retry-After` header within the maximum wait
- **WHEN** the request is made
- **THEN** the system SHALL wait the indicated seconds and retry

### Requirement: Record scheduled run outcomes
The system SHALL record the outcome of each scheduled daily run as a persistent history entry
capturing the run's start and finish times, its trigger, the discovery counters (repositories
discovered, newly enabled, archived skipped), and the sync counters (enqueued, skipped, failed).

#### Scenario: A scheduled run is recorded
- **WHEN** the daily scheduled job completes
- **THEN** a history entry SHALL be recorded with its timestamps and discovery/sync counters

#### Scenario: History is listable newest-first
- **WHEN** the recorded scheduled runs are read
- **THEN** they SHALL be returned most-recent first

### Requirement: Scheduled runs skip sync-disabled organizations
The scheduled discovery and sync SHALL skip any repository whose owning organization is
sync-disabled. A repository whose organization is sync-enabled, or whose organization is not yet
recorded, SHALL be unaffected (fail-open). The scheduled sync SHALL count repositories skipped for
this reason in its run summary, and the scheduled auto-enable SHALL NOT enable a newly-discovered
repository in a sync-disabled organization.

#### Scenario: Repositories in a disabled organization are not synced
- **GIVEN** an organization whose sync is disabled
- **WHEN** the scheduled sync runs
- **THEN** enabled repositories in that organization SHALL NOT be enqueued

#### Scenario: Repositories in an enabled organization still sync
- **GIVEN** an organization whose sync is enabled
- **WHEN** the scheduled sync runs
- **THEN** its enabled repositories SHALL be enqueued as before

#### Scenario: Unknown organization is fail-open
- **GIVEN** a repository whose organization has no record yet
- **WHEN** the scheduled sync runs
- **THEN** the repository SHALL be treated as in scope and synced

#### Scenario: Auto-enable respects organization scope
- **GIVEN** a newly-discovered non-archived repository in a sync-disabled organization
- **WHEN** scheduled discovery runs
- **THEN** that repository SHALL NOT be auto-enabled

### Requirement: On-demand full sync

The system SHALL let an admin trigger an immediate sync of all enabled
repositories, optionally scoped to a single organization, reusing the per-repo
enqueue path (holding the per-repository lock so an already-running sync is
skipped, and continuing past individual failures). It SHALL report how many
repositories were enqueued and how many were skipped.

#### Scenario: Sync all enabled repositories
- **WHEN** an admin triggers an on-demand full sync
- **THEN** a sync SHALL be enqueued for each enabled repository not already running, and the counts of enqueued and skipped SHALL be returned

#### Scenario: Scoped to an organization
- **WHEN** an admin triggers an on-demand sync scoped to an organization
- **THEN** only that organization's enabled repositories SHALL be enqueued

