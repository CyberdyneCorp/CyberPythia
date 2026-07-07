Feature: Repository documentation ingestion

  Scenario: Synced docs are captured, classified, and searchable
    Given the Mnemosyne API is running
    And the repository "cyberdyne/matforge" has been synced
    Then the README.md is captured as type "README"
    And OpenSpec change "add-gpu-backend" is indexed with its proposal
    And a semantic search for "gpu backend kernels" returns "docs/gpu-backend.md"
