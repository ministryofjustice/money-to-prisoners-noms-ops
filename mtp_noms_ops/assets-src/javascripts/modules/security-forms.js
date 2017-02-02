// Security module
/* globals prisonData */
'use strict';

exports.SecurityForms = {
  init: function () {
    $('#id_ordering').change(function () {
      $(this).closest('form').submit();
    });

    this.bindAmountPatternSelection();
    this.bindPaymentSourceSelection();
    this.bindPrisonSelection();
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
  },

  bindPrisonSelection: function () {
    var $prisonOptions = $('#id_prison option');
    $prisonOptions.each(function () {
      var $option = $(this);
      var nomisID = $option.val();
      if (!nomisID) {
        return;
      }
      $option.data(prisonData[nomisID] || {});
    });

    var $regionSelect = $('#id_prison_region');
    var $categorySelect = $('#id_prison_category');
    var $populationSelect = $('#id_prison_population');

    function update () {
      var selectedRegion = $regionSelect.val();
      var selectedCategory = $categorySelect.val();
      var selectedPopulation = $populationSelect.val();

      $prisonOptions.each(function () {
        var $option = $(this);
        if (!$option.val()) {
          return;
        }
        var optionData = $option.data();
        /* eslint-disable no-extra-parens */
        var optionDisabled = (
          (selectedRegion && optionData.region && optionData.region !== selectedRegion) ||
          (selectedCategory && !optionData.categories[selectedCategory]) ||
          (selectedPopulation && !optionData.populations[selectedPopulation])
        );
        /* eslint-enable no-extra-parens */
        $option.prop('disabled', optionDisabled);
      });
    }

    $regionSelect.change(update);
    $categorySelect.change(update);
    $populationSelect.change(update);
    update();
  }
};
