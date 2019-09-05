'use strict';

var analytics = require('analytics');

exports.FormAnalytics = {
  init: function () {
    $('.js-FormAnalytics').each(this.bindForm);
  },

  bindForm: function () {
    var $form = $(this);
    var formId = $form.attr('id');
    var initialInputs = $form.find(":input:not(:hidden)").serializeArray();

    function sendEvent (category, action, label) {
      analytics.Analytics.send(
        'event', category, action, label
      );
    }

    $form.on('submit', function (e) {
      // send event for every changed form field name
      var inputs = $form.find(":input:not(:hidden)").serializeArray();
      var nonEmptyFilters = [];
      $.each(inputs, function () {
        var changed = true;
        for (var i = 0; i < initialInputs.length; i++) {
          if (initialInputs[i].name === this.name &&
              initialInputs[i].value === this.value) {
            changed = false;
          }
        }
        if (this.value) {
          nonEmptyFilters.push(this.name);

          if (changed) {
            // TODO: delete after search V2 goes live ?
            sendEvent('SecurityFormsFilter', formId, this.name);
          }
          sendEvent('SecurityForms', formId, this.name);  // TODO: delete after search V2 goes live.

          // send one event per filter
          sendEvent('form-submitted-single-filter', formId, this.name);
        }
      });

      // send also an event for all combined filters used
      if (nonEmptyFilters.length) {
        sendEvent('form-submitted-combined-filters', formId, nonEmptyFilters.sort().join(','));
      }
    });

    $('.js-FormAnalytics-click', $form[0]).click(function () {
      // send click event, e.g. for print or export
      var $element = $(this);
      var eventDetails = $element.data('click-track').split(',');
      if (eventDetails.length === 2) {
        sendEvent('form-link', eventDetails[0], eventDetails[1]);

        // TODO: delete after search V2 goes live.
        sendEvent('SecurityFormsExport', eventDetails[0], eventDetails[1]);

        analytics.Analytics.rawSend(
          'pageview',
          $element.attr('href').split('?')[0]
        );
      }
    });
  }
};
