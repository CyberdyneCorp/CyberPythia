# web-ui Specification

## Purpose
TBD - created by archiving change add-github-context-memory-core. Update Purpose after archive.
## Requirements
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

### Requirement: Code Context tab
The repository detail page SHALL include a Code Context tab that, for repositories indexed in a code mode, provides a semantic code-search box returning ranked symbol results (file path, symbol, chunk type, line span, excerpt) and an on-demand source-content viewer. For repositories not indexed for code, the tab SHALL display a message explaining that source code is not indexed and how to enable it.

#### Scenario: Search code from the UI
- **WHEN** a user enters a query in the Code Context search box for a `code_context` repository
- **THEN** ranked source-chunk results SHALL render, each linking to the file and line span, and selecting one SHALL show its captured content

#### Scenario: Non-code repository
- **WHEN** a user opens the Code Context tab for a `project_intelligence` repository
- **THEN** the tab SHALL explain that source code is not indexed and name the mode required to enable it

### Requirement: GitHub App connection screen (admin)
The admin GitHub connection area SHALL let an admin register a GitHub App installation (app id, installation id, App private key, webhook secret), alongside the existing PAT flow, and trigger installation-repository discovery. Secret fields SHALL be masked and never re-displayed after submission.

#### Scenario: Admin registers an App installation
- **WHEN** an admin submits App installation credentials
- **THEN** the UI SHALL show validation results (resolved owner) and enable discovery, without echoing the private key or webhook secret

### Requirement: Webhook activity panel
The admin area SHALL display recent webhook deliveries (event, action, repository, outcome, time) so an admin can confirm near-real-time updates are flowing.

#### Scenario: View recent deliveries
- **WHEN** an admin opens the webhook activity panel after events have arrived
- **THEN** recent deliveries SHALL be listed with their event type, target repository, and outcome

### Requirement: Intelligence dashboard
The web UI SHALL provide an Intelligence dashboard route presenting the portfolio overview: a health-ranked repository leaderboard (score + grade), the most-active repositories, abandoned repositories, and bug-heavy repositories. Repositories without metrics SHALL be shown with an insufficient-data indicator. All list renders SHALL use stable keys.

#### Scenario: Portfolio dashboard loads
- **GIVEN** an authenticated user with the `mnemosyne` entitlement
- **WHEN** they open the Intelligence dashboard
- **THEN** the health leaderboard and the most-active, abandoned, and bug-heavy groupings SHALL be displayed

#### Scenario: Repository lacking metrics
- **GIVEN** an enabled repository that has not been synced
- **WHEN** the dashboard renders
- **THEN** that repository SHALL show an insufficient-data indicator rather than a fabricated score

### Requirement: Repository health panel
The web UI SHALL present, on the repository detail page, a health panel showing the repository's overall score, letter grade, per-component breakdown, and findings.

#### Scenario: Health panel on repository detail
- **GIVEN** a synced repository
- **WHEN** the user opens its detail page
- **THEN** the health panel SHALL show the overall score, grade, component sub-scores, and findings

#### Scenario: Component with unknown inputs
- **GIVEN** a repository whose indexing mode does not capture a file tree
- **WHEN** the health panel renders
- **THEN** the testing/CI component SHALL be shown as not-applicable rather than as a zero score

### Requirement: Delivery dashboard view
The web UI SHALL provide a Delivery view on the Intelligence dashboard presenting, across the
portfolio, throughput and net-flow trends, backlog forecasts, work-mix distribution, and
at-risk milestones. Charts SHALL be self-contained (no external chart dependency). Repositories
or metrics lacking data SHALL show an insufficient-data indicator. All list and chart renders
SHALL use stable keys.

#### Scenario: Delivery view loads
- **GIVEN** an authenticated user with the `mnemosyne` entitlement
- **WHEN** they open the Delivery view
- **THEN** throughput/net-flow, backlog forecast, work-mix, and at-risk milestones SHALL be displayed

#### Scenario: History still collecting
- **GIVEN** a repository without enough snapshots for a trend
- **WHEN** the Delivery view renders it
- **THEN** it SHALL show a "collecting history" indicator instead of a fabricated trend

### Requirement: Repository delivery panel
The web UI SHALL present, on the repository detail page, a delivery panel showing cycle/lead
percentiles, WIP and aging, work-mix, and milestone progress for that repository.

#### Scenario: Delivery panel on repository detail
- **GIVEN** a synced repository with closed work
- **WHEN** the user opens its detail page
- **THEN** the delivery panel SHALL show percentiles, WIP/aging, work-mix, and milestone progress

#### Scenario: Metric with no data
- **GIVEN** a repository with no merged PRs
- **WHEN** the delivery panel renders
- **THEN** the affected metric SHALL be shown as insufficient data rather than zero

### Requirement: Organizations sync panel
The web UI SHALL present, on the GitHub Connection page, an Organizations panel listing each
discovered organization with its repository counts (total / enabled) and a control to enable or
disable sync for that organization. Toggling SHALL persist immediately.

#### Scenario: Admin disables an organization from the UI
- **GIVEN** the Organizations panel lists several organizations
- **WHEN** the admin turns off sync for one organization
- **THEN** that organization SHALL be persisted as sync-disabled and reflected in the panel

### Requirement: Organization filter on the Repositories dashboard
The Repositories dashboard SHALL provide an organization filter that restricts the listed
repositories to a chosen organization, combining with the existing text filter. The available
organizations SHALL be derived from the loaded repositories.

#### Scenario: Filter the dashboard by organization
- **GIVEN** the dashboard lists repositories from several organizations
- **WHEN** the user selects one organization in the filter
- **THEN** only that organization's repositories SHALL be shown

#### Scenario: Clearing the organization filter
- **WHEN** the user clears the organization filter
- **THEN** repositories from all organizations SHALL be shown again

### Requirement: Enable-all / Disable-all on the Repositories dashboard
The Repositories dashboard SHALL provide controls to enable or disable indexing for all
repositories currently shown (after the organization and text filters are applied), with a mode
selection for the enable action. Applying a bulk action SHALL update the shown repositories in
place.

#### Scenario: Enable all filtered repositories
- **GIVEN** the dashboard is filtered to one organization
- **WHEN** the admin chooses Enable all with a mode
- **THEN** every repository in that filtered view SHALL become enabled in the chosen mode

#### Scenario: Disable all filtered repositories
- **WHEN** the admin chooses Disable all
- **THEN** every repository in the filtered view SHALL become disabled

### Requirement: Index-all / Un-index-all per organization
The Organizations panel SHALL provide, per organization, controls to index (enable) or un-index
(disable) all of that organization's repositories at once, with a mode selection for indexing. The
organization's repository counts SHALL update after the action.

#### Scenario: Un-index an organization from the panel
- **GIVEN** the Organizations panel lists an organization with indexed repositories
- **WHEN** the admin chooses Un-index all for it
- **THEN** all of that organization's repositories SHALL become disabled and the counts SHALL reflect it

### Requirement: API key management panel

The web UI SHALL provide an admin panel (on the Connections screen) to generate,
list, and revoke Mnemosyne API keys. Generating a key SHALL let the admin enter a
label and choose an expiry from presets (including "never"). On creation the UI
SHALL display the plaintext key once with a copy affordance and a warning that it
will not be shown again. The panel SHALL list existing keys with label, display
prefix, expiry, and state, and SHALL offer a revoke action per key.

#### Scenario: Generate and reveal once
- **WHEN** an admin submits the generate form with a label and expiry
- **THEN** the UI SHALL show the new plaintext key with a copy button and a "shown once" warning, and add the key to the list

#### Scenario: Revoke from the list
- **WHEN** an admin clicks revoke on a listed key
- **THEN** the UI SHALL revoke the key and reflect it as revoked in the list

### Requirement: Global search page

The web UI SHALL provide a search page (`/search`, linked in the nav) that searches
across all indexed repositories by kind — documentation, code, issues, or
repositories — with an optional organization scope. Results SHALL link to the
relevant repository; code results SHALL render the matched snippet with its file
path and line.

#### Scenario: Search across repositories
- **WHEN** a user enters a query on the search page and picks a kind
- **THEN** the UI SHALL show ranked results across repositories, each linking to its repository

#### Scenario: Code snippet results
- **WHEN** the selected kind is code
- **THEN** each result SHALL show the matched snippet with its `path:line`

### Requirement: Organization-scoped Intelligence view

The Intelligence page SHALL provide an organization filter that scopes the health
leaderboard and delivery scorecard **server-side**, and SHALL show, when an
organization is selected, an organization overview card (rollup) plus recent-activity
and needs-attention (stale issues/PRs) panels for that scope.

#### Scenario: Scoping the Intelligence page
- **WHEN** a user selects an organization in the Intelligence filter
- **THEN** the leaderboard, scorecard, overview card, and activity/stale panels SHALL reflect only that organization

### Requirement: Repository capabilities tab

The repository detail page SHALL provide a Capabilities tab showing the project's
capabilities, bug count, issue/PR counts, and documentation topics, with an action
to generate and display a grounded Markdown feature document.

#### Scenario: View capabilities and generate a feature document
- **WHEN** a user opens the Capabilities tab and requests a feature document
- **THEN** the UI SHALL show the capability overview and render the generated Markdown document

