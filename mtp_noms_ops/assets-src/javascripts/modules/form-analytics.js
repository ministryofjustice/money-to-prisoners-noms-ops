'use strict';

var analytics = require('analytics');

exports.FormAnalytics = {
  init: function () {
    $('.js-FormAnalytics').each(this.bindForm);
  },

  bindForm: function () {
    var $form = $(this);
    var formId = $form.attr('id');
    var location = $form.data('ga-location');
    var page = $form.data('ga-page');
    var title = $form.data('ga-title');

    function sendEvent (action, label) {
      analytics.Analytics.send(
        'event', {
          eventCategory: 'SecurityForms',
          eventAction: action,
          eventLabel: label,
          location: location,
          page: page,
          title: title
        }
      );
    }

    $form.on('submit', function () {
      // send event for every used form field name
      var inputs = $form.serializeArray();
      $.each(inputs, function () {
        if (this.value) {
          sendEvent(formId, this.name);
        }
      });
    });

    $('.js-FormAnalytics-click', $form[0]).click(function () {
      // send click event, e.g. for print or export
      var $element = $(this);
      var eventDetails = $element.data('click-track').split(',');
      if (eventDetails.length === 2) {
        sendEvent(eventDetails[0], eventDetails[1]);
      }
    });
  }
};
