Feature: Uploading
  As a signed-in user
  I want to be able to access the uploads page
  And upload a file
  So that the system has my file

  Scenario: go to the upload page
    Given I am signed in
    And I go to the "Upload" page
    Then I should see "Upload location file"

  Scenario: upload a valid file
    Given I am signed in
    And I go to the "Upload" page
    And I select a valid CSV file to upload
    And I submit the form
    Then I should see "File uploaded successfully!"

  Scenario: upload an invalid file
    Given I am signed in
    And I go to the "Upload" page
    And I select an invalid CSV file to upload
    And I submit the form
    Then I should see "Row has 5 columns, should have 4"

  Scenario: submit the file upload without selecting a file
    Given I am signed in
    And I go to the "Upload" page
    And I submit the form
    Then I should see "This field is required"
