// As-you-type formatting of sort codes
'use strict';

exports.ChoosePrisons = {
  init: function () {
    var $form = $('form.mtp-choose-prison');
    if ($form.length !== 1) {
      return;
    }
    var $hiddenInputs = $form.find('input.mtp-autocomplete-hidden');
    var $chooseButton = $form.find('button[name=submit_choose]');
    $chooseButton.click(function (e) {
      var someEmpty = false;
      $hiddenInputs.each(function () {
        var $input = $(this);
        if (!$input.val()) {
          $input.data('visualInput').addClass('form-control-error');
          var $inputFormGroup = $input.data('visualInput').parents('.form-group')
          $inputFormGroup.addClass('form-group-error');
          $inputFormGroup.children('.error-message').remove();
          var empty_error = $input.data('autocomplete-error-empty');
          if (empty_error) {
            $input.data('visualInput').before(
              '<span class="error-message">' + empty_error + '</span>'
            );
          }
          someEmpty = true;
        }
      });
      if (someEmpty) {
        e.preventDefault();
        return false;
      }
      return true;
    });
  }
};
