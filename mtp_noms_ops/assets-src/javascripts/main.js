(function () {
  'use strict';
  require('polyfills').Polyfills.init();
  require('gds-modules').GDSModules.init();

  require('dialogue-box').DialogueBox.init();
  require('upload').Upload.init();
  require('print').Print.init();
  require('analytics').Analytics.init();
  require('mailcheck-warning').MailcheckWarning.init(
    '.mtp-account-management input[type=email]',
    ['hmps.gsi.gov.uk', 'noms.gsi.gov.uk', 'justice.gsi.gov.uk'],
    ['gsi.gov.uk', 'gov.uk']
  );
  require('notifications').Notifications.init();
  require('async-load').AsyncLoad.init();
  require('date-picker').DatePicker.init();

  require('confirm-checked').ConfirmChecked.init();
  require('security-forms').SecurityForms.init();
  require('autocomplete-select').AutocompleteSelect.init();
  require('choose-prisons').ChoosePrisons.init();
  require('form-analytics').FormAnalytics.init();
}());
