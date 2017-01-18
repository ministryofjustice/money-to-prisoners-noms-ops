// Security module
'use strict';

exports.SecurityForms = {
  init: function () {
    $('#id_ordering').change(function () {
      $(this).closest('form').submit();
    });

    this.bindAmountPatternSelection();
    this.bindPaymentSourceSelection();
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
  },

  bindPaymentSourceSelection: function () {
    var $paymentSourceSelect = $('#id_source');
    var $senderAccountNumber = $('#id_sender_account_number-wrapper');
    var $senderSortCode = $('#id_sender_sort_code-wrapper');
    var $cardNumberLastDigits = $('#id_card_number_last_digits-wrapper');

    function update () {
      switch ($paymentSourceSelect.val()) {
        case 'bank_transfer':
          $senderAccountNumber.show();
          $senderSortCode.show();
          $cardNumberLastDigits.hide();
          break;
        case 'online':
          $senderAccountNumber.hide();
          $senderSortCode.hide();
          $cardNumberLastDigits.show();
          break;
        default:
          $senderAccountNumber.hide();
          $senderSortCode.hide();
          $cardNumberLastDigits.hide();
      }
    }

    $paymentSourceSelect.change(update);
    update();
  }
};
