/* globals GOVUK */
'use strict';

exports.GDSModules = {
  init: function () {
    window.jQuery = $;

    require('govuk_frontend_toolkit/javascripts/govuk/show-hide-content');
    (new GOVUK.ShowHideContent()).init();

    window.jQuery = undefined;
  }
};
