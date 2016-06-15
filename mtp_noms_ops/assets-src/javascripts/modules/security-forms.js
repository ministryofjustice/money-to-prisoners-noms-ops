// Security module
/* globals exports, $ */
'use strict';

exports.SecurityForms = {
  init: function () {
    $('#id_ordering').change(function () {
      $(this).closest('form').submit();
    });

    this.bindAmountPatternSelection();
    this.bindCreditDetailLoading();
  },

  bindAmountPatternSelection: function() {
    var $patternSelect = $('#id_amount_pattern'),
      $exactWrapper = $('#id_amount_exact-wrapper'),
      $penceWrapper = $('#id_amount_pence-wrapper');

    function update() {
      switch ($patternSelect.val()) {
        case 'exact':
          $exactWrapper.show();
          $penceWrapper.hide();
          break;
        case 'pence':
          $exactWrapper.hide();
          $penceWrapper.show();
          break;
        default:
          $exactWrapper.hide();
          $penceWrapper.hide();
      }
    }

    $patternSelect.change(update);
    update();
  },

  bindCreditDetailLoading: function() {
    var creditRowClass = 'CreditDetailRow';

    function creditToggle(e) {
      var $link = $(e.target);
      var showTitle = $link.data('show-title');
      var loadingTitle = $link.data('loading-title');
      var hideTitle = $link.data('hide-title');
      var state = $link.data('credit-detail');

      function loadCreditDetails(html) {
        var $thisRow = $link.closest('tr'),
          $creditList = $(html).find('.ResultsList'),
          $creditRow = $('<tr></tr>').addClass(creditRowClass).addClass($thisRow.attr('class')),
          $creditCell = $('<td></td>'),
          columns = 0;

        $creditList.find('caption').remove();
        $creditList.find('.CollapsingTable').removeClass('CollapsingTable');
        $creditList.find('tr th:first-of-type, tr td:first-of-type').each(function() {
          $(this).remove();
        });
        $thisRow.find('td').each(function () {
          columns += parseInt($(this).attr('colspan') || '1', 10);
        });
        $creditRow.append(
          $creditCell.append($creditList).attr('colspan', columns)
        );
        $thisRow.after($creditRow);

        $link.text(hideTitle);
        $link.data('credit-detail', 'loaded');
      }

      function removeCreditDetails() {
        var $creditDetailsRow = $link.closest('tr').next();

        if ($creditDetailsRow.hasClass(creditRowClass)) {
          $creditDetailsRow.remove();
        }

        $link.text(showTitle);
        $link.data('credit-detail', '');
      }

      e.preventDefault();
      if (state === 'loaded') {
        // remove credit details

        removeCreditDetails();
      } else if (state !== 'loading') {
        // load credit details

        $link.text(loadingTitle);
        $link.data('credit-detail', 'loading');
        $.ajax({
          url: $link.attr('href'),
          dataType: 'html'
        }).then(
          // load credit details table if ajax works
          loadCreditDetails,
          // remove credit details if fails to load
          removeCreditDetails
        );
      }
    }

    $('.CreditDetailLink').each(function() {
      $(this).click(creditToggle);
    });
  }
};
