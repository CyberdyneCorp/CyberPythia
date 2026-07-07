# web-ui — Code Context tab

## ADDED Requirements

### Requirement: Code Context tab
The repository detail page SHALL include a Code Context tab that, for repositories indexed in a code mode, provides a semantic code-search box returning ranked symbol results (file path, symbol, chunk type, line span, excerpt) and an on-demand source-content viewer. For repositories not indexed for code, the tab SHALL display a message explaining that source code is not indexed and how to enable it.

#### Scenario: Search code from the UI
- **WHEN** a user enters a query in the Code Context search box for a `code_context` repository
- **THEN** ranked source-chunk results SHALL render, each linking to the file and line span, and selecting one SHALL show its captured content

#### Scenario: Non-code repository
- **WHEN** a user opens the Code Context tab for a `project_intelligence` repository
- **THEN** the tab SHALL explain that source code is not indexed and name the mode required to enable it
