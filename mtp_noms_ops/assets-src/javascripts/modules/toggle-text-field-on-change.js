
'use strict';

exports.ToggleTextFieldOnChange = {
  selector: '.js-ToggleTextFieldOnChange',

  init: function () {
    $(this.selector).each(function () {
      if ($(this).prop('checked')) {
        var dataTarget = $(this).parent('div').data('target');
        $('[name=' + dataTarget).prop('disabled', false).parent('div').removeClass('js-hidden');
      }
      $(this).change(function () {
        var dataTarget = $(this).parent('div').data('target');
        $('[name=' + dataTarget).prop(
          'disabled',
          function (_, v) {
            return !v;
          }
        ).parent('div').toggleClass('js-hidden');
      });
    });
  }
};
