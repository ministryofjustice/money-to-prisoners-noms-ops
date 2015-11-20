Feature: Signing in
  As a user
  I want to be able to sign in
  So that I can access the system

  Scenario: Successful sign in
    Given I am on the "Sign in" page
    When I sign in with "prisoner_location_admin" and "prisoner_location_admin"
    Then I should see "Logged in as Prisoner Location Admin"
    And I should see "Upload location file"
