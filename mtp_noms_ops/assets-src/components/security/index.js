'use strict';

export var Security = {
  init: function () {
    this.initReviewCredits();
  },

  initReviewCredits: function () {
    $('.mtp-review').on('click', ':submit', function (e) {
      // Called when the user submits the form,
      // either clicking 'Done' or 'Yes' in the popup.
      var $el = $(e.target);
      var type = $el.val();

      if (type !== 'submit') {
        // If this is a 'Yes' click in the confirmation popup, so just
        // actually submit
        return;
      }

      e.preventDefault();
      $('#confirm-checked').trigger('dialogue:open');
    });
  }
};
