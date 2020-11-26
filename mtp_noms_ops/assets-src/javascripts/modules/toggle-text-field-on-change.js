
'use strict';

exports.ToggleTextFieldOnChange = {
  selector: '.js-ToggleTextFieldOnChange',

  init: function () {
    $(this.selector).each(function () {
      this.onchange = function() {
        $(this).parent('div').find('textarea').toggleClass('ignore-input');
      };
    });
  }
};


