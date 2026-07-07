Feature: MCP tools for agents

  Scenario: Agent lists repositories and reads context over MCP
    Given the Mnemosyne API is running
    And the repository "cyberdyne/matforge" has been synced
    When an agent connects to the MCP server with a valid token
    Then the MCP tool list includes the mnemosyne tool suite
    And calling "mnemosyne_get_repository_summary" returns the matforge summary
    And calling "mnemosyne_get_readme" returns the README content

  Scenario: MCP rejects an unauthenticated agent
    Given the Mnemosyne API is running
    When an agent connects to the MCP server without a token
    Then MCP tool calls fail with an authentication error
