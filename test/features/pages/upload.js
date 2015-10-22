/* jshint node: true */

'use strict';

/*
 * upload.js
 *
 * Upload page object
 * Detaches UI interactions from step definitions
 *
 */
var UploadPage = function (client) {

  this.get = function (callback) {
    client
      .url('/')
      .call(callback);
  };

};

module.exports = {
  class: UploadPage,
  name: 'Upload'
};
