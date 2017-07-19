(function () {
  'use strict';
  require('polyfills').Polyfills.init();

  require('dialogue-box').DialogueBox.init();
  require('upload').Upload.init();
  require('proposition-header').PropositionHeader.init();
  require('print').Print.init();
  require('analytics').Analytics.init();

  require('confirm-checked').ConfirmChecked.init();
  require('security-forms').SecurityForms.init();
  require('tabs').Tabs.init();
}());
