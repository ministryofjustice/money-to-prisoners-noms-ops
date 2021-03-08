'use strict';

export var CheckboxWithConditionalSubfields = {
  init: function () {
    $('.mtp-checkbox-with-conditional-subfields .govuk-checkboxes__input').each(function () {
      // find all checkboxes with conditional content inside a checkbox group
      var $checkbox = $(this);
      var conditionalContentTarget = $checkbox.data('aria-controls') || $checkbox.attr('aria-controls');
      if (conditionalContentTarget) {
        var $conditionalContent = $('#' + conditionalContentTarget);
        if ($conditionalContent.length === 1) {
          // find all fields in conditional content
          var $subfields = $('input, textarea', $conditionalContent[0]);

          // eslint-disable-next-line no-inner-declarations
          function updateSubfields () {
            if ($checkbox.prop('checked')) {
              // if containing checkbox is checked, make subfields required
              $subfields.prop('required', true);
              $subfields.prop('disabled', false);
            } else {
              // if containing checkbox is checked, make subfields disabled
              $subfields.prop('required', false);
              $subfields.prop('disabled', true);
            }
          }

          $checkbox.change(updateSubfields);
          updateSubfields();
        }
      }
    });
  }
};
