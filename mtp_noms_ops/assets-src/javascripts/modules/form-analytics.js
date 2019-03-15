'use strict';

var analytics = require('analytics');

exports.FormAnalytics = {
  selector: '.js-FormAnalytics',

  init: function () {
    this.cacheEls();
    this.bindEvents();
  },

  cacheEls: function () {
    this.$form = $(this.selector);
  },

  bindEvents: function () {
    this.$form.on('submit', this.onSubmit);
  },

  onSubmit: function () {
    var $form = $(this);
    var inputs = $form.serializeArray();
    var formId = $form.attr('id');
    var location = $form.data('ga-location');
    var page = $form.data('ga-page');
    var title = $form.data('ga-title');

    $.each(inputs, function () {
      if (this.value) {
        analytics.Analytics.send(
          'event', {
            eventCategory: 'SecurityForms',
            eventAction: formId,
            eventLabel: this.name,
            location: location,
            page: page,
            title: title
          }
        );
      }
    });
  }
};
