// Batch validation module
/* global exports, $ */
'use strict';

exports.ConfirmChecked = {
  selector: '.js-ConfirmChecked',

  init: function () {
    this.cacheEls();
    this.bindEvents();
  },

  cacheEls: function () {
    this.$body = $('body');
    this.$form = $(this.selector);
  },

  bindEvents: function () {
    this.$body.on('ConfirmChecked.render', this.render);
    this.$form.on('click', ':submit', $.proxy(this.onSubmit, this));
  },

  // Called when the user submits the form,
  // either clicking 'Done' or 'Yes' in the popup.
  onSubmit: function (e) {
    var $el = $(e.target);
    var type = $el.val();

    if(type !== 'submit') {
      // If this is a 'Yes' click in the confirmation popup, so just
      // actually submit
      return;
    }

      e.preventDefault();
      this.$body.trigger({
        type: 'Dialog.render',
        target: e.target,
        targetSelector: '#confirm-checked'
      });
      return;
  }
};
