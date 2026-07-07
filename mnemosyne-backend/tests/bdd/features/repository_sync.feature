Feature: Repository sync
  A GitHub organization becomes an AI-readable memory once its
  repositories are connected, discovered, enabled, and synced.

  Scenario: Admin connects GitHub and syncs a repository
    Given the Mnemosyne API is running
    And a GitHub credential with repository read permissions is connected
    And the repository "cyberdyne/matforge" is enabled with mode "project_intelligence"
    When the admin starts a repository sync
    Then the sync completes successfully
    And the repository summary reports a README and OpenSpec content

  Scenario: Non-admin cannot trigger a sync
    Given the Mnemosyne API is running
    And a GitHub credential with repository read permissions is connected
    And the repository "cyberdyne/matforge" is enabled with mode "project_intelligence"
    When a non-admin user tries to start a sync
    Then the request is rejected with status 403

  Scenario: Caller without the mnemosyne entitlement is rejected
    Given the Mnemosyne API is running
    When a caller without the mnemosyne entitlement lists repositories
    Then the request is rejected with status 403
