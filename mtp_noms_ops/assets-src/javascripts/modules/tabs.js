'use strict';

exports.Tabs = {
  init: function () {
    this.bindEvents($('.mtp-tab'));
  },

  bindEvents: function ($tabButtons) {
    if ($tabButtons.length === 0) {
      return;
    }

    var selectedIndex = null;
    var $tabContainer = $tabButtons.closest('.mtp-tab-container');
    var $tabPanels = $tabContainer.find('.mtp-tabpanel');
    var $tabPanelContainer = $tabPanels.closest('.mtp-tabpanels');

    function resetTabsAndPanels () {
      $tabButtons.attr({
        tabindex: '-1',
        'aria-selected': 'false'
      }).removeClass('mtp-tab--selected');
      $tabPanels.hide();
    }

    resetTabsAndPanels();

    $tabButtons.each(function () {
      var $tabButton = $(this);
      var $tabPanel = $($tabButton.attr('href'));
      $tabButton.data('mtp-tabpanel', $tabPanel);
      $tabPanel.data('mtp-tab', $tabButton);
    });
    $tabButtons.on('click', function (e) {
      var $tabButton = $(this);
      var wasSelected = $tabButton.hasClass('mtp-tab--selected');

      resetTabsAndPanels();

      if (wasSelected) {
        selectedIndex = null;
        $tabContainer.addClass('mtp-tab-container--collapsed');
        $tabPanelContainer.attr('aria-expanded', 'false');
      } else {
        selectedIndex = $tabButtons.index($tabButton);
        $tabButton.attr({
          tabindex: '0',
          'aria-selected': 'true'
        }).addClass('mtp-tab--selected');
        $tabButton.data('mtp-tabpanel').show();
        $tabContainer.removeClass('mtp-tab-container--collapsed');
        $tabPanelContainer.attr('aria-expanded', 'true');
      }

      e.preventDefault();
    });

    $tabContainer.on('keydown', '.mtp-tab', function (e) {
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

    var $tabPanelsWithErrors = $tabPanels.has('.error-message');
    $tabPanelsWithErrors.each(function () {
      var $tabPanel = $(this);
      $tabPanel.data('mtp-tab').addClass('error-message');
    });
    $tabPanelsWithErrors.first().data('mtp-tab').click();
  }

};
