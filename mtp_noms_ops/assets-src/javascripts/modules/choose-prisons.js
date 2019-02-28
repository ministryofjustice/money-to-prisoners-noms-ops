'use strict';

var analytics = require('analytics');

exports.ChoosePrisons = {
  init: function () {
    var $form = $('form.mtp-choose-prison');
    if ($form.length !== 1) {
      return;
    }

    var selected_prisons = this.selected_prisons();
    analytics.Analytics.send(
      'event', {
        eventCategory: 'PrisonConfirmation',
        eventAction: 'Selected',
        eventLabel: selected_prisons
      }
    );

    var $hiddenInput = $form.find('input.mtp-autocomplete-hidden');
    var $chooseButton = $form.find('button[name=submit_choose]');

    $chooseButton.click(function (e) {
      var no_selection = false;
      if (!$hiddenInput.val()) {
        $hiddenInput.data('visualInput').addClass('form-control-error');
        var $hiddenInputFormGroup = $hiddenInput.data('visualInput').parents('.form-group')
        $hiddenInputFormGroup.addClass('form-group-error');
        $hiddenInputFormGroup.children('.error-message').remove();
        $('div.error-summary').remove()
        var empty_error_msg = $hiddenInput.data('autocomplete-error-empty');
        var error_summary_title = $hiddenInput.data('autocomplete-error-summary');
        if (empty_error_msg) {
          $hiddenInput.data('visualInput').before(
            '<span class="error-message">' + empty_error_msg + '</span>'
          );

          var label = $('label[for=' + $hiddenInput.data('visualInput').attr('id') + ']');
          var label_text = label.contents().get(0).nodeValue;
          $('div.mtp-prison-list').before(
            '<div class="error-summary" aria-labeledby="error-summary-heading" tabindex="-1" role="alert">' +
            '  <h2 class="heading-medium error-summary-heading" id="error-summary-heading">' + error_summary_title + '</h2>' +
            '  <ul class="error-summary-list">' +
            '      <li class="field-specific-error">' +
            '        <a href="#id_new_prison-label">' + empty_error_msg + '</a>' +
            '      </li>' +
            '  </ul>' +
            '</div>'
          );

          analytics.Analytics.send(
            'event', {
              eventCategory: 'security.forms.preferences.ChoosePrisonForm',
              eventAction: 'new_prison',
              eventLabel: empty_error_msg
            }
          );
        }
        no_selection = true;
      }

      if (no_selection) {
        e.preventDefault();
        return false;
      }

      analytics.Analytics.send(
        'event', {
          eventCategory: 'PrisonConfirmation',
          eventAction: 'Add',
          eventLabel: $hiddenInput.val()
        }
      );
      return true;
    });

    var $confirmButton = $form.find('button[name=submit_confirm]');
    var self = this;
    $confirmButton.click(function (e) {
      var new_prisons_str = self.selected_prisons();

      if ($hiddenInput.val()) {
        new_prisons_str = new_prisons_str + ' + ' + $hiddenInput.val();
      }

      var event_label = $confirmButton.data('current-prisons') + ' > ' + new_prisons_str;
      analytics.Analytics.send(
        'event', {
          eventCategory: 'PrisonConfirmation',
          eventAction: 'Confirm',
          eventLabel: event_label
        }
      );
    });
  },

  selected_prisons: function () {
    var new_prisons = [];
    var $chosen_prisons = $('form.mtp-choose-prison').find(
      'input[name=prisons]:checked'
    );
    $chosen_prisons.each(function() {
      var $chosen_prison = $(this);
      new_prisons.push($chosen_prison.val());
    });
    var new_prisons_str = new_prisons.join(',');
    return new_prisons_str;
  }
};



