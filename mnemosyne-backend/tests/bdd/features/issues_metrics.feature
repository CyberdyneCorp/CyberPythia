Feature: Issue capture and metrics

  Scenario: Issues are synced and resolution metrics computed
    Given the Mnemosyne API is running
    And the repository "cyberdyne/matforge" has been synced
    Then the issue list contains issue 42 in state "closed"
    And the average issue resolution time is 4 days
