'use strict';

exports.Tabs = {
  init: function () {
    this.bindEvents($('a.tab'));
  },

  bindEvents: function ($tabButtons) {
    if ($tabButtons.length === 0) {
      return;
    }

    var selectedIndex = null;
    var $tabContainer = $tabButtons.closest('.tabs');
    var $tabPanels = $tabContainer.find('.tabcontent');

    function resetTabButtons () {
      $tabButtons.attr({
        tabindex: '-1',
        'aria-selected': 'false'
      }).removeClass('selected');
      $tabPanels.hide();
    }

    resetTabButtons();

    $tabButtons.each(function () {
      $(this).on('click', function (e) {
        var $tabButton = $(this);
        var wasSelected = $tabButton.hasClass('selected');

        resetTabButtons();

        if (wasSelected) {
          selectedIndex = null;
          $tabContainer.addClass('collapsed-tabs');
        } else {
          selectedIndex = $tabButtons.index($tabButton);
          $tabButton.attr({
            tabindex: '0',
            'aria-selected': 'true'
          }).addClass('selected');
          $($tabButton.attr('href')).show();
          $tabContainer.removeClass('collapsed-tabs');
        }

        e.preventDefault();
      });
    });

    $tabContainer.on('keydown', 'a.tab', function (e) {
      var key = e.which;

      if (selectedIndex === null || key < 37 || key > 40) {
        return;
      }

      var maxIndex = $tabButtons.length - 1;

      if (key === 37 || key === 38) {
        if (selectedIndex > 0) {
          selectedIndex--;
        } else {
          selectedIndex = maxIndex;
        }
      } else if (key === 39 || key === 40) {
        if (selectedIndex < maxIndex) {
          selectedIndex++;
        } else {
          selectedIndex = 0;
        }
      }
      $($tabButtons[selectedIndex]).focus().click();

      e.preventDefault();
    });
  }

};
