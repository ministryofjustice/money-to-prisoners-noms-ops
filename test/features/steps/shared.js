/* jshint node: true */

'use strict';

/*
 * shared.js
 *
 * Provides shared step definitions
 *
 */
var sharedSteps = function(){

  /**
   * Go to a url of a page object
   *
   * Usage: Given I am on the "Signin" page
   * Usage: Given I go to the "Signin" page
   *
   * @params {string} page The requested page object name
   * @params {function} next The callback function of the scenario
   */
  this.Given(/^I (?:am on|go to) the "([^"]*)" page$/, function(pageName, next) {
    if (!browser.pages[pageName]) {
      throw new Error('Could not find page with name "' + pageName + '" in the PageObjectMap, did you remember to add it?');
    }

    var page = new browser.pages[pageName](browser);
    page.get(next);
  });

  /**
   * Choose a CSV file to upload
   *
   * Usage: When I select a valid file to upload
   * Usage: When I select an invalid file to upload
   * @params {string} valid "a valid" if the file to be uploaded is valid
   */
  this.When(/^I select (a valid|an invalid) CSV file to upload$/, function(valid, next) {
    var fileName = (valid === 'a valid') ? 'valid.csv' : 'invalid.csv';
    browser
      .chooseFile('#id_location_file',
        process.cwd() + '/test/features/' + fileName, next);
  });

  /**
   * Submit an upload form
   *
   * Usage: When I submit the upload form
   */
  this.When(/^I submit the form$/, function(next) {
    browser.submitForm('form.js-uploadSubmit', next);
  });

  /**
   * Check if a link exists
   *
   * Usage: Then I should see a "Click here" link to  "/file.txt"
   * @params {string} linkText the text of the link
   * @params {string} linkTarget the text of the link's target
   */
  this.Then(/^I should see a "([^"]+)" link to "([^"]+)"$/, function (linkText, linkTarget, next) {
    browser
      .getSource('body')
      .should.eventually.contain('<a href="' + linkTarget + '/">' + linkText + '</a>')
      .and.notify(next);
  });

  /**
   * Check the current body content contains
   * supplied text
   *
   * Usage: Then I should see "some text"
   *
   * @params {string} text The text to check for
   * @params {function} next The callback function of the scenario
   */
  this.Then(/^I should see "([^"]*)"$/, function(text, next) {
    browser
      .getText('body')
      .should.eventually.contain(text)
      .and.notify(next);
  });

  /**
   * Check the current body content does not
   * contain supplied text
   *
   * Usage: Then I should not see "some text"
   *
   * @params {string} text The text to check on
   * @params {function} next The callback function of the scenario
   */
  this.Then(/^I should not see "([^"]*)"$/, function(text, next) {
    browser
      .getText('body')
      .should.eventually.not.contain(text)
      .and.notify(next);
  });

  /**
   * Check the current page title matches
   * supplied title
   *
   * Usage: Then I should "some title" as the page title
   *
   * @params {string} text The title to check for
   * @params {function} next The callback function of the scenario
   */
  this.Then(/^I should see "([^"]*)" as the page title$/, function(title, next) {
    browser
      .getTitle()
      .should.eventually.equal(title)
      .and.notify(next);
  });

};

module.exports = sharedSteps;
