'use strict';

var analytics = require('analytics');
var autocomplete = require('autocomplete-select');

exports.ChoosePrisons = {
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
    analytics.Analytics.send(
      'event', 'PrisonConfirmation', 'Change', currentPrisons
    );

    this.setupInputs();
  },

  setupInputs: function () {
    var $form = $('form.mtp-choose-prison');
    var $hiddenInputs = $form.find('input.mtp-autocomplete-hidden');

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
              '        <a href="#id_' + $hiddenInput.attr('name') + '-label">' + emptyErrorMsg + '</a>' +
              '      </li>' +
              '  </ul>' +
              '</div>'
            );

            analytics.Analytics.send(
              'event',
              'security.forms.preferences.ChoosePrisonForm',
              'new_prison',
              emptyErrorMsg
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
        'event', 'PrisonConfirmation', 'Save', addedPrisons
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
        'event', 'PrisonConfirmation', 'Confirm', event_label
      );
    });
  },

  initAddPrison: function() {
    var $form = $('form.mtp-choose-prison');
    if ($form.length !== 1) {
      return;
    }
    var self = this;

    var $addPrisonLink = $form.find('input[name=submit_add]');
    $addPrisonLink.click(function (e) {
      var next_prison_id = 0;
      $('.mtp-prison-selection-row').each(function () {
        var thisId = parseInt($(this).attr('id').substring(11));
        if (thisId >= next_prison_id) {
          next_prison_id = thisId + 1;
        }
      });

      var template = $('#prison-field-template').html().replace(
        /template_prison_selection/g,
        'prison_' + next_prison_id
      );
      var $newRow = $(template);
      $newRow.addClass('hidden');
      $('.mtp-prison-selection').append($newRow);
      autocomplete.AutocompleteSelect.replaceSelect.call($newRow.find('select'));
      self.setupInputs();
      self.initRemovePrison();
      $newRow.removeClass('hidden');

      e.preventDefault();
      return false;
    });
  },

  initRemovePrison: function() {
    var $form = $('form.mtp-choose-prison');
    if ($form.length !== 1) {
      return;
    }

    var $removalLinks = $form.find('.mtp-prison-selection-row__remove > input');
    $removalLinks.each(function () {
      var $removalLink = $(this);
      var related_field_name = $removalLink.attr('name').substring(14);
      $removalLink.click(function (e) {
        $form.find('#row_' + related_field_name).remove();

        var $errorSummary = $form.find('div.error-summary');
        if ($errorSummary.length > 0) {
          var $fieldErrors = $errorSummary.find('li.field-specific-error');
          $fieldErrors.each(function () {
            var $link = $(this).find('a');
            if ($link.attr('href') == ('#id_' + related_field_name + '-label')) {
              $(this).remove();
            }

            if ($errorSummary.find('li.field-specific-error').length == 0 &&
                $errorSummary.find('li.non-field-error').length == 0) {
              $form.find('div.error-summary').remove();
            }
          });
        }

        e.preventDefault();
        return false;
      });
    });
  }
};



