# web-ui — Svelte 5 MVVM dashboard

## ADDED Requirements

### Requirement: MVVM architecture
The web UI SHALL be built with Svelte 5 and TypeScript following MVVM: views (Svelte components) SHALL bind to viewmodels, viewmodels SHALL orchestrate API clients and hold presentation state, and models SHALL mirror API schemas. Views SHALL NOT call API clients directly.

#### Scenario: Data flow for repository list
- **WHEN** the repository dashboard loads
- **THEN** the view SHALL render state exposed by `RepositoryListViewModel`, which fetches via the repositories API client

### Requirement: Cyberdyne sign-in
The UI SHALL present a "Connect with Cyberdyne" sign-in (per the auth capability's OIDC flow) and SHALL show the signed-in user's identity. Users without the `mnemosyne` entitlement SHALL see an access-denied screen naming the required entitlement, not a broken dashboard.

#### Scenario: Unentitled user signs in
- **WHEN** a user authenticates but lacks the `mnemosyne` entitlement
- **THEN** the UI SHALL display an access-denied page with guidance to request access

### Requirement: GitHub connection screen (admin)
The UI SHALL provide an admin screen to register a fine-grained PAT, display its detected permissions, test the connection, and trigger repository discovery. This screen SHALL be hidden from non-admin users.

#### Scenario: Admin connects GitHub
- **WHEN** an admin submits a PAT on the connection screen
- **THEN** the UI SHALL show validation results (owner, permissions) and enable discovery

### Requirement: Repository dashboard
The UI SHALL show discovered repositories as cards with name, description, language, selection/mode state, last sync, issue and PR counts, and documentation presence. Admins SHALL be able to enable/disable indexing, set the indexing mode, and trigger sync from the dashboard, with visible sync progress.

#### Scenario: Sync progress
- **WHEN** an admin triggers a sync
- **THEN** the card SHALL show live sync status until the job completes or fails

### Requirement: Repository detail
The UI SHALL provide a repository detail page with tabs: Overview (summary), Documentation (rendered markdown incl. README/docs), OpenSpec (changes with proposal/tasks/design), Issues (table with filters), Pull Requests (table with filters), Files (tree, when captured), Metrics (issue/PR analytics), and Agent Context (context-pack builder).

#### Scenario: Documentation tab
- **WHEN** a user opens the Documentation tab of a synced repository
- **THEN** captured documents SHALL be listed by type and render as formatted markdown

### Requirement: Context-pack builder and ask
The UI SHALL let a user enter a task or question for a repository and display either the generated context pack (grouped relevant docs, OpenSpec changes, issues, PRs, files, risks, next steps) or the grounded answer with clickable source citations.

#### Scenario: PM asks a question
- **WHEN** a user submits "what is blocking the current release?" on the Agent Context tab
- **THEN** the UI SHALL display the answer with citations linking to the referenced issues/PRs/docs within the app
