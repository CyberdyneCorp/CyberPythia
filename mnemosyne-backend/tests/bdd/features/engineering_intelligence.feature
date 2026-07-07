Feature: Engineering intelligence

  Scenario: A synced repository is scored for health
    Given the Mnemosyne API is running
    And the repository "cyberdyne/matforge" has been synced
    Then the repository health report has a grade and an overall score
    And the portfolio overview includes the repository

  Scenario: A synced repository exposes PM/PO delivery flow metrics
    Given the Mnemosyne API is running
    And the repository "cyberdyne/matforge" has been synced
    Then the delivery flow report has cycle-time percentiles and work-in-progress
    And the repository has at least one captured milestone
