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
    this.$form.on('submit', $.proxy(this.onSubmit, this));
  },

  onSubmit: function () {
    var inputs = this.$form.serializeArray();
    var formId = this.$form.attr('id');

    $.each(inputs, function () {
      if (this.value) {
        analytics.Analytics.send(
          'event', {
            eventCategory: 'SecurityForms',
            eventAction: formId,
            eventLabel: this.name
          }
        );
      }
    });
  }
};
