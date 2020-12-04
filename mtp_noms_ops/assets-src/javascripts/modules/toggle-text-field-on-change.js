
'use strict';

exports.ToggleTextFieldOnChange = {
  selector: '.js-ToggleTextFieldOnChange',

  init: function () {
    $(this.selector).each(function () {
      if ($(this).prop('checked')) {
        let dataTarget = $(this).parent('div').data('target');
        $(`[name=${dataTarget}]`).prop('disabled', false).parent('div').removeClass('js-hidden');
      };
      this.onchange = function() {
        let dataTarget = $(this).parent('div').data('target');
        $(`[name=${dataTarget}]`).prop('disabled', function(i, v) { return !v; }).parent('div').toggleClass('js-hidden');
      };
    });
  }
};
