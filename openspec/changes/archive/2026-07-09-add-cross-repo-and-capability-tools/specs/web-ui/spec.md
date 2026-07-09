# web-ui Specification

## ADDED Requirements

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
