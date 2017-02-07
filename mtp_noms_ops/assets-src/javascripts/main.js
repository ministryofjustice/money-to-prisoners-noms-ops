(function () {
  'use strict';
  require('confirm-checked').ConfirmChecked.init();
  require('dialog').Dialog.init();
  require('tabs').Tabs.init();
  require('security-forms').SecurityForms.init();

  require('upload').Upload.init();
  require('proposition-header').PropositionHeader.init();
  require('help-popup').HelpPopup.init();
  require('print').Print.init();
  require('analytics').Analytics.init();
  require('polyfills').Polyfills.init();
  require('selection-buttons').SelectionButtons.init();
}());
