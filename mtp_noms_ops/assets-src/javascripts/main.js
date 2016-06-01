/* globals require */

(function() {
  'use strict';

  var Mojular = require('mojular');

  Mojular
    .use([
      require('mojular-govuk-elements'),
      require('mojular-moj-elements'),
      require('polyfills'),
      require('collapsing-table'),
      require('upload'),
      
      require('security-forms')
    ])
    .init();
}());
