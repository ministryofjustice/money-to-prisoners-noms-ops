(function () {
  'use strict';

  // common
  require('upload').Upload.init();
  require('print').Print.init();
  require('mailcheck-warning').MailcheckWarning.init(
    '.mtp-account-management input[type=email]',
    ['justice.gov.uk'],
    ['gov.uk']
  );
  require('async-load').AsyncLoad.init();

  // noms-ops
  require('confirm-checked').ConfirmChecked.init();
  require('autocomplete-select').AutocompleteSelect.init();
  require('choose-prisons').ChoosePrisons.init();
  require('form-analytics').FormAnalytics.init();
  require('toggle-text-field-on-change').ToggleTextFieldOnChange.init();
}());
