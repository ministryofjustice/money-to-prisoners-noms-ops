(function () {
  'use strict';

  // common
  require('upload').Upload.init();

  // noms-ops
  require('confirm-checked').ConfirmChecked.init();
  require('autocomplete-select').AutocompleteSelect.init();
  require('choose-prisons').ChoosePrisons.init();
  require('form-analytics').FormAnalytics.init();
  require('toggle-text-field-on-change').ToggleTextFieldOnChange.init();
}());
