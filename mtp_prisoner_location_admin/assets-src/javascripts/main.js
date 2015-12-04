/* globals require, console */

(function() {
  'use strict';

  var Mojular = require('mojular');

  Mojular
    .use([
      require('mojular-govuk-elements'),
      require('mojular-moj-elements'),
      require('dialog'),
      require('batch-validation'),
      require('feature-tour'),
      require('messages'),
      require('print'),
      require('polyfills'),
      require('unload')
    ])
    .init();
}());
