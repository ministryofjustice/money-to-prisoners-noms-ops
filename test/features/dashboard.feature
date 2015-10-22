Feature: Signing in
  As a signed-in user
  I want to be able to access the uploads page from the dashboard
  So that I can go and upload files

  Scenario: Go to the upload page
    Given I am signed in
    And I go to the "Dashboard" page
    Then I should see a "Update prisoner locations" link to "/upload"
