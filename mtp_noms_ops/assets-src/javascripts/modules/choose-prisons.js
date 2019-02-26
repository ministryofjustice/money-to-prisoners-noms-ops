// As-you-type formatting of sort codes
'use strict';

exports.ChoosePrisons = {
  init: function () {
    var $form = $('form.mtp-choose-prison');
    if ($form.length !== 1) {
      return;
    }
    var $hiddenInput = $form.find('input.mtp-autocomplete-hidden');
    var $chooseButton = $form.find('button[name=submit_choose]');
    $chooseButton.click(function (e) {
      var someEmpty = false;
      if (!$hiddenInput.val()) {
        $hiddenInput.data('visualInput').addClass('form-control-error');
        var $hiddenInputFormGroup = $hiddenInput.data('visualInput').parents('.form-group')
        $hiddenInputFormGroup.addClass('form-group-error');
        $hiddenInputFormGroup.children('.error-message').remove();
        $('div.error-summary').remove()
        var empty_error_msg = $hiddenInput.data('autocomplete-error-empty');
        var error_summary_title = $hiddenInput.data('autocomplete-error-summary');
        if (empty_error_msg) {
          $hiddenInput.data('visualInput').before(
            '<span class="error-message">' + empty_error_msg + '</span>'
          );

          var label = $('label[for=' + $hiddenInput.data('visualInput').attr('id') + ']');
          var label_text = label.contents().get(0).nodeValue;
          $('div.mtp-prison-list').before(
            '<div class="error-summary" aria-labeledby="error-summary-heading" tabindex="-1" role="alert">' +
            '  <h2 class="heading-medium error-summary-heading" id="error-summary-heading">' + error_summary_title + '</h2>' +
            '  <ul class="error-summary-list">' +
            '      <li class="field-specific-error">' +
            '        <a href="#id_new_prison-label">' + label_text + '</a>' +
            '        <ul>' +
            '            <li>' + empty_error_msg + '</li>' +
            '        </ul>' +
            '      </li>' +
            '  </ul>' +
            '</div>'
          );
        }
        someEmpty = true;
      }

      if (someEmpty) {
        e.preventDefault();
        return false;
      }
      return true;
    });
  }
};



