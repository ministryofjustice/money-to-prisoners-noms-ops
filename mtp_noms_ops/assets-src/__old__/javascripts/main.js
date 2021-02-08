(function () {
  'use strict';

  // common
  require('dialogue-box').DialogueBox.init();
  require('upload').Upload.init();
  require('print').Print.init();
  require('tabbed-panel').TabbedPanel.init();
  require('mailcheck-warning').MailcheckWarning.init(
    '.mtp-account-management input[type=email]',
    ['justice.gov.uk'],
    ['gov.uk']
  );
  require('notifications').Notifications.init();
  require('async-load').AsyncLoad.init();
  require('date-picker').DatePicker.init();

  // noms-ops
  require('confirm-checked').ConfirmChecked.init();
  require('security-forms').SecurityForms.init();
  require('autocomplete-select').AutocompleteSelect.init();
  require('choose-prisons').ChoosePrisons.init();
  require('form-analytics').FormAnalytics.init();
  require('disable-on-submit').DisableOnSubmit.init();
  require('toggle-text-field-on-change').ToggleTextFieldOnChange.init();
}());
