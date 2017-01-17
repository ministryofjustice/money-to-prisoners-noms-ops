(function () {
  'use strict';
  require('tabs').Tabs.init();

  require('proposition-header').PropositionHeader.init();
  require('upload').Upload.init();
  require('analytics').Analytics.init();
  require('help-popup').HelpPopup.init();
  require('selection-buttons').SelectionButtons.init();
  require('print').Print.init();
  require('dialog').Dialog.init();

  require('security-forms').SecurityForms.init();
  require('confirm-checked').ConfirmChecked.init();
}());
