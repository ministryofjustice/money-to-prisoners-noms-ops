'use strict';

var analytics = require('analytics');

exports.ChoosePrisons = {
  init: function () {
    this.initChangePrisons();
    this.initConfirmPrisons();
  },

  initChangePrisons: function () {
    var $form = $('form.mtp-choose-prison');
    if ($form.length !== 1) {
      return;
    }

    var $hiddenInputs = $form.find('input.mtp-autocomplete-hidden');
    var currentPrisons = '';
    if ($form.find('input[name=all_prisons]:checked')) {
      currentPrisons = 'ALL';
    } else {
      currentPrisons = this.addedPrisons($hiddenInputs);
    }
    analytics.Analytics.send(
      'event', {
        eventCategory: 'PrisonConfirmation',
        eventAction: 'Change',
        eventLabel: currentPrisons
      }
    );

    $form.find('input[type=text]').keydown(function(e) {
      if (e.keyCode === 13) {
        e.preventDefault();
        return false;
      }
    });

    var $saveButton = $form.find('button[name=submit_save]');
    var self = this;
    $saveButton.click(function (e) {
      var noSelection = false;

      $hiddenInputs.each(function () {
        var $hiddenInput = $(this);
        var $visualInput = $('input#id_' + $hiddenInput.attr('name'));
        // error if they type something but don't select anything
        if (!$hiddenInput.val() && $visualInput.val()) {
          $hiddenInput.data('visualInput').addClass('form-control-error');
          var $hiddenInputFormGroup = $hiddenInput.data('visualInput').parents('.form-group');
          $hiddenInputFormGroup.addClass('form-group-error');
          $hiddenInputFormGroup.find('.error-message').remove();
          $('div.error-summary').remove();
          var emptyErrorMsg = $hiddenInput.data('autocomplete-error-empty');
          var errorSummaryTitle = $hiddenInput.data('autocomplete-error-summary');
          if (emptyErrorMsg) {
            $hiddenInput.data('visualInput').before(
              '<span class="error-message">' + emptyErrorMsg + '</span>'
            );

            $('div.mtp-prison-selection').before(
              '<div class="error-summary" aria-labeledby="error-summary-heading" tabindex="-1" role="alert">' +
              '  <h2 class="heading-medium error-summary-heading" id="error-summary-heading">' + errorSummaryTitle + '</h2>' +
              '  <ul class="error-summary-list">' +
              '      <li class="field-specific-error">' +
              '        <a href="#' + $hiddenInput.attr('id') + '-label">' + emptyErrorMsg + '</a>' +
              '      </li>' +
              '  </ul>' +
              '</div>'
            );

            analytics.Analytics.send(
              'event', {
                eventCategory: 'security.forms.preferences.ChoosePrisonForm',
                eventAction: 'new_prison',
                eventLabel: emptyErrorMsg
              }
            );
          }
          noSelection = true;
        }
      });

      if (noSelection) {
        e.preventDefault();
        return false;
      }

      var addedPrisons = '';
      if ($form.find('input[name=all_prisons]:checked')) {
        addedPrisons = 'ALL';
      } else {
        addedPrisons = self.addedPrisons($hiddenInputs);
      }
      analytics.Analytics.send(
        'event', {
          eventCategory: 'PrisonConfirmation',
          eventAction: 'Save',
          eventLabel: addedPrisons
        }
      );
      return true;
    });
  },

  addedPrisons: function(inputs) {
    var newPrisons = [];
    inputs.each(function () {
      var $input = $(this);
      newPrisons.push($input.val());
    });
    return newPrisons.join(',');
  },

  initConfirmPrisons: function () {
    var $form = $('form.mtp-confirm-prison');
    var self = this;
    if ($form.length !== 1) {
      return;
    }

    var $confirmButton = $form.find('button[name=submit_save]');
    $confirmButton.click(function () {
      var $chosenPrisons = $form.find('input[name=prisons]:checked');
      var newPrisonsStr = self.addedPrisons($chosenPrisons);

      var event_label = $confirmButton.data('current-prisons') + ' > ' + newPrisonsStr;
      analytics.Analytics.send(
        'event', {
          eventCategory: 'PrisonConfirmation',
          eventAction: 'Confirm',
          eventLabel: event_label
        }
      );
    });
  }
};



