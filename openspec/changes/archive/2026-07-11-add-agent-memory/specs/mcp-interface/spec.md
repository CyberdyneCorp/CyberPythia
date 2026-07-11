# mcp-interface Specification

## ADDED Requirements

### Requirement: Memory MCP tools

The MCP server SHALL expose `mnemosyne_remember(content, full_name?, organization?,
kind?)` to record a memory, `mnemosyne_recall(full_name?, organization?, query?,
kind?, limit?)` to list a scope's memories newest-first, and
`mnemosyne_forget(memory_id)` to delete one. These are available to entitled
callers (memory writes go only to Mnemosyne, not GitHub).

#### Scenario: Remember and recall
- **WHEN** a caller invokes `mnemosyne_remember` for a repository and then `mnemosyne_recall`
- **THEN** recall SHALL return the recorded memory

#### Scenario: Forget
- **WHEN** a caller invokes `mnemosyne_forget` with a memory id
- **THEN** the memory SHALL no longer be returned by recall
