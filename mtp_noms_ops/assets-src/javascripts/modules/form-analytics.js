'use strict';

var analytics = require('analytics');

exports.FormAnalytics = {
  init: function () {
    $('.js-FormAnalytics').each(this.bindForm);
  },

  bindForm: function () {
    var $form = $(this);
    var formId = $form.attr('id');
    var initialInputs = $form.serializeArray();

    function sendEvent (category, action, label) {
      analytics.Analytics.send(
        'event', category, action, label
      );
    }

    $form.on('submit', function () {
      // send event for every changed form field name
      var inputs = $form.serializeArray();
      $.each(inputs, function () {
        var changed = true;
        for (var i = 0; i < initialInputs.length; i++) {
          if (initialInputs[i].name === this.name &&
              initialInputs[i].value === this.value) {
            changed = false;
          }
        }
        if (this.value) {
          if (changed) {
            sendEvent('SecurityFormsFilter', formId, this.name);
          }
          sendEvent('SecurityForms', formId, this.name);
        }
      });
    });

    $('.js-FormAnalytics-click', $form[0]).click(function () {
      // send click event, e.g. for print or export
      var $element = $(this);
      var eventDetails = $element.data('click-track').split(',');
      if (eventDetails.length === 2) {
        sendEvent('SecurityFormsExport', eventDetails[0], eventDetails[1]);

        analytics.Analytics.rawSend(
          'pageview',
          $element.attr('href').split('?')[0]
        );
      }
    });
  }
};
