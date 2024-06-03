// track form submissions (only field names are sent for privacy)
'use strict';

import {Analytics} from 'mtp_common/components/analytics';

export var FormAnalytics = {
  init: function () {
    $('.mtp-form-analytics').each(this.bindForm);
  },

  bindForm: function () {
    var $form = $(this);
    var formId = $form.attr('id');

    function sendEvent (category, action, label) {
      Analytics.ga4SendEvent(category, action, label);
    }

    $form.on('submit', function () {
      // send event for every changed form field name
      var inputs = $form.find(':input:not(:hidden)').serializeArray();
      var nonEmptyFilters = [];
      $.each(inputs, function () {
        if (this.value) {
          nonEmptyFilters.push(this.name);

          // send one event per filter
          sendEvent('form-submitted-single-filter', formId, this.name);
        }
      });

      // send also an event for all combined filters used
      if (nonEmptyFilters.length) {
        sendEvent('form-submitted-combined-filters', formId, nonEmptyFilters.sort().join(','));
      }
    });

    $('.mtp-form-analytics__click', $form[0]).click(function () {
      // send click event, e.g. for print or export
      var $element = $(this);
      var eventDetails = $element.data('click-track').split(',');
      var clickAsPageview = Boolean($element.data('click-as-pageview'));
      if (eventDetails.length === 2) {
        sendEvent('form-link', eventDetails[0], eventDetails[1]);

        if (clickAsPageview) {
          var pageLocation = $element.attr('href').split('?')[0];
          Analytics.ga4SendPageView(pageLocation);
        }
      }
    });
  }
};
