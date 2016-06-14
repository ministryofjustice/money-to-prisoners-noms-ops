// Security module
/* globals exports, $ */
'use strict';

exports.SecurityForms = {
  init: function () {
    $('#id_ordering').change(function () {
      $(this).closest('form').submit();
    });

    this.bindAmountPatternSelection();
  },

  bindAmountPatternSelection: function() {
    var $patternSelect = $('#id_amount_pattern'),
      $exactWrapper = $('#id_amount_exact-wrapper'),
      $penceWrapper = $('#id_amount_pence-wrapper');

    function update() {
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
