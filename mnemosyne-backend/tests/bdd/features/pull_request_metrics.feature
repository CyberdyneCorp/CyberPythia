Feature: Pull request capture and metrics

  Scenario: PRs are synced with review timings
    Given the Mnemosyne API is running
    And the repository "cyberdyne/matforge" has been synced
    Then the pull request list contains merged PR 61 reviewed by "carol"
    And the average PR merge time is 2 days
