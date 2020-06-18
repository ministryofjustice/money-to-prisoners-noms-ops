// Disables forms on submit – used to prevent accidental concurrent submissions
// NB: this temporary component will be replaced by a built-in one once this app is upgraded to the GDS design system
'use strict';

exports.DisableOnSubmit = {
  selector: '.js-DisableOnSubmit',

  init: function () {
    $(this.selector).each(function () {
      var $button = $(this);
      var $form = $button.closest('form');

      $form.submit(function () {
        $button.prop('disabled', true);
      });
    });
  }
};
