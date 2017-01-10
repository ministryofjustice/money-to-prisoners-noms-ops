'use strict';

exports.Tabs = {

  init: function () {
    this.bindEvents();
  },

  bindEvents: function () {
    var $tabs = $('a.tab');
    var index = 0;

    function setFocus () {
      $tabs.attr({
        tabindex: '-1',
        'aria-selected': 'false'
      }).removeClass('selected');

      $('.tabcontent').addClass('hidden');

      $($tabs.get(index)).attr({
        tabindex: '0',
        'aria-selected': 'true'
      }).addClass('selected').focus();

      $($($tabs.get(index)).attr('href')).removeClass('hidden');
    }

    $tabs.on('keydown', function (e) {
      var k = e.which || e.keyCode;

      if (k >= 37 && k <= 40) {
        if (k === 37 || k === 38) {
          if (index > 0) {
            index--;
          } else {
            index = $tabs.length - 1;
          }
        } else if (k === 39 || k === 40) {
          if (index < $tabs.length - 1) {
            index++;
          } else {
            index = 0;
          }
        }

        $($tabs.get(index)).click();
        e.preventDefault();
      }
    });

    $tabs.on('click', function (e) {
      index = $.inArray(this, $tabs.get());
      setFocus();
      e.preventDefault();
    });

  }
};
