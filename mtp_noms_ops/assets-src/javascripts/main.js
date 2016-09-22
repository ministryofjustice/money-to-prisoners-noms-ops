/* globals require */

(function () {
  'use strict';
  require('upload').Upload.init();
  require('analytics').Analytics.init();
  require('help-popup').HelpPopup.init();
  require('collapsing-table').CollapsingTable.init();
  require('selection-buttons').SelectionButtons.init();

  require('security-forms').SecurityForms.init();
})();
