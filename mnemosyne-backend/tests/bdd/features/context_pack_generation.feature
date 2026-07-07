Feature: Agent context pack generation

  Scenario: Agent requests context for a repository task
    Given the Mnemosyne API is running
    And the repository "cyberdyne/matforge" has been synced
    When an agent requests a context pack for "implement OpenCL backend"
    Then the context pack includes relevant docs
    And the context pack includes issue 42
    And the context pack includes pull request 61
    And the context pack includes OpenSpec change "add-gpu-backend"

  Scenario: Agent asks a grounded question about the repository
    Given the Mnemosyne API is running
    And the repository "cyberdyne/matforge" has been synced
    When an agent asks "how does the GPU backend work?"
    Then the answer is grounded with source citations
