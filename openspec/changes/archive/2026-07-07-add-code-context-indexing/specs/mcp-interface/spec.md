# mcp-interface — code tools

## ADDED Requirements

### Requirement: Code MCP tools
The MCP server SHALL expose: `mnemosyne_get_file_content`, `mnemosyne_search_code`, `mnemosyne_get_symbol_context`, `mnemosyne_get_related_files`, and `mnemosyne_explain_repository_structure`. Each SHALL require the `mnemosyne` entitlement and return structured errors; tools that need source content SHALL return a `mode_excludes_content` error for repositories not indexed for code, and `repository_not_synced` for unsynced repositories.

#### Scenario: Agent searches code
- **WHEN** an entitled agent calls `mnemosyne_search_code` for a `code_context` repository
- **THEN** it SHALL receive ranked source-chunk matches with file, symbol, line span, and excerpt

#### Scenario: Code tool on non-code repository
- **WHEN** an agent calls `mnemosyne_get_file_content` or `mnemosyne_search_code` for a repository indexed below `code_context`
- **THEN** the tool SHALL return a `mode_excludes_content` structured error

#### Scenario: Explain repository structure
- **WHEN** an agent calls `mnemosyne_explain_repository_structure` for a synced repository
- **THEN** it SHALL receive a summary of the tree, primary languages, important files, and (for code modes) key modules/symbols
