(function () {
  'use strict';
  require('polyfills').Polyfills.init();

  require('dialogue-box').DialogueBox.init();
  require('upload').Upload.init();
  require('proposition-user-menu').PropositionUserMenu.init();
  require('print').Print.init();
  require('analytics').Analytics.init();
  require('tabbed-panel').TabbedPanel.init();

  require('confirm-checked').ConfirmChecked.init();
  require('security-forms').SecurityForms.init();
}());
