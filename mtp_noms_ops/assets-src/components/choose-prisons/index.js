'use strict';

import {Analytics} from 'mtp_common/components/analytics';
import {AutocompleteSelect} from 'mtp_common/components/autocomplete-select';

export var ChoosePrisons = {
  init: function () {
    this.initChangePrisons();
    this.initConfirmPrisons();
    this.initAddPrison();
    this.initRemovePrison();
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
    var eventCategory = 'PrisonConfirmation';
    var eventAction = 'Change';
    var eventLabel = currentPrisons;
    Analytics.send('event', eventCategory, eventAction, eventLabel);
    Analytics.ga4SendEvent(eventCategory, eventAction, eventLabel);

    this.setupInputs();
  },

  setupInputs: function () {
    var $form = $('form.mtp-choose-prison');
    var $hiddenInputs = $form.find('input.mtp-autocomplete-hidden');

    $form.find('input[type=text]').keydown(function (e) {
      if (e.which === 13) {
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
          $hiddenInput.data('visualInput').addClass('govuk-input--error');
          var $hiddenInputFormGroup = $hiddenInput.data('visualInput').parents('.govuk-form-group');
          $hiddenInputFormGroup.addClass('govuk-form-group--error');
          $hiddenInputFormGroup.find('.govuk-error-message').remove();
          $('.govuk-error-summary').remove();
          var emptyErrorMsg = $hiddenInput.data('autocomplete-error-empty');
          var errorSummaryTitle = $hiddenInput.data('autocomplete-error-summary');
          if (emptyErrorMsg) {
            $hiddenInput.data('visualInput').before(
              '<p class="govuk-error-message">' + emptyErrorMsg + '</p>'
            );

            $('.mtp-prison-selection').before(
              '<div class="govuk-error-summary" aria-labeledby="error-summary-title__prison-selection"' +
              ' role="alert" data-module="govuk-error-summary">' +
              '<h2 class="govuk-error-summary__title" id="error-summary-title__prison-selection">' +
              errorSummaryTitle +
              '</h2>' +
              '<div class="govuk-error-summary__body">' +
              '  <ul class="govuk-list govuk-error-summary__list">' +
              '    <li class="mtp-error-summary__field-error">' +
              '      <a href="#id_' + $hiddenInput.attr('name') + '-label">' + emptyErrorMsg + '</a>' +
              '    </li>' +
              '  </ul>' +
              '</div>' +
              '</div>'
            );

            var eventCategory = 'security.forms.preferences.ChoosePrisonForm';
            var eventAction = 'new_prison';
            var eventLabel = emptyErrorMsg;
            Analytics.send('event', eventCategory, eventAction, eventLabel);
            Analytics.ga4SendEvent(eventCategory, eventAction, eventLabel);
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
      var eventCategory = 'PrisonConfirmation';
      var eventAction = 'Save';
      var eventLabel = addedPrisons;
      Analytics.send('event', eventCategory, eventAction, eventLabel);
      Analytics.ga4SendEvent(eventCategory, eventAction, eventLabel);
      return true;
    });
  },

  addedPrisons: function (inputs) {
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

      var eventCategory = 'PrisonConfirmation';
      var eventAction = 'Confirm';
      var eventLabel = $confirmButton.data('current-prisons') + ' > ' + newPrisonsStr;
      Analytics.send('event', eventCategory, eventAction, eventLabel);
      Analytics.ga4SendEvent(eventCategory, eventAction, eventLabel);
    });
  },

  initAddPrison: function () {
    var $form = $('form.mtp-choose-prison');
    if ($form.length !== 1) {
      return;
    }
    var self = this;

    var $addPrisonLink = $form.find('input[name=submit_add]');
    $addPrisonLink.click(function (e) {
      var nextPrisonId = 0;
      $('.mtp-prison-selection-row').each(function () {
        var thisId = parseInt($(this).attr('id').substring(11), 10);
        if (thisId >= nextPrisonId) {
          nextPrisonId = thisId + 1;
        }
      });

      var template = $('#prison-field-template').html().replace(
        /template_prison_selection/g,
        'prison_' + nextPrisonId
      );
      var $newRow = $(template);
      $newRow.addClass('hidden');
      $('.mtp-prison-selection').append($newRow);
      AutocompleteSelect.replaceSelect.call($newRow.find('select'));
      self.setupInputs();
      self.initRemovePrison();
      $newRow.removeClass('hidden');

      e.preventDefault();
      return false;
    });
  },

  initRemovePrison: function () {
    var $form = $('form.mtp-choose-prison');
    if ($form.length !== 1) {
      return;
    }

    var $removalLinks = $form.find('.mtp-prison-selection-row__remove input');
    $removalLinks.each(function () {
      var $removalLink = $(this);
      var relatedFieldName = $removalLink.attr('name').substring(14);
      $removalLink.click(function (e) {
        $form.find('#row_' + relatedFieldName).remove();

        var $errorSummary = $form.find('.govuk-error-summary');
        if ($errorSummary.length > 0) {
          var $fieldErrors = $errorSummary.find('li.mtp-error-summary__field-error');
          $fieldErrors.each(function () {
            var $link = $(this).find('a');
            if ($link.attr('href') === '#id_' + relatedFieldName + '-label') {
              $(this).remove();
            }

            if ($errorSummary.find('li.mtp-error-summary__field-error').length === 0 &&
                $errorSummary.find('li.mtp-error-summary__non-field-error').length === 0) {
              $form.find('.govuk-error-summary').remove();
            }
          });
        }

        e.preventDefault();
        return false;
      });
    });
  }
};
