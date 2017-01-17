// Security module
'use strict';

exports.SecurityForms = {
  init: function () {
    $('#id_ordering').change(function () {
      $(this).closest('form').submit();
    });

    this.bindAmountPatternSelection();
  },

  bindAmountPatternSelection: function () {
    var $patternSelect = $('#id_amount_pattern');
    var $exactWrapper = $('#id_amount_exact-wrapper');
    var $penceWrapper = $('#id_amount_pence-wrapper');

    function update () {
      switch ($patternSelect.val()) {
        case 'exact':
          $exactWrapper.show();
          $penceWrapper.hide();
          break;
        case 'pence':
          $exactWrapper.hide();
          $penceWrapper.show();
          break;
        default:
          $exactWrapper.hide();
          $penceWrapper.hide();
      }
    }

    $patternSelect.change(update);
    update();
  }
};
