(function () {
  'use strict';
  require('polyfills').Polyfills.init();

  require('dialogue-box').DialogueBox.init();
  require('upload').Upload.init();
  require('proposition-user-menu').PropositionUserMenu.init();
  require('print').Print.init();
  require('analytics').Analytics.init();
  require('tabbed-panel').TabbedPanel.init();
  require('mailcheck-warning').MailcheckWarning.init(
    '.mtp-account-management input[type=email]',
    ['hmps.gsi.gov.uk', 'noms.gsi.gov.uk', 'justice.gsi.gov.uk'],
    ['gsi.gov.uk', 'gov.uk']
  );

  require('confirm-checked').ConfirmChecked.init();
  require('security-forms').SecurityForms.init();
}());
