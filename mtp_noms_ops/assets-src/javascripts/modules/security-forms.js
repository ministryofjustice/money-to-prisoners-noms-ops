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
    var $patternSelect = $('#id_amount_pattern');
    var $exactWrapper = $('#id_amount_exact-wrapper');
    var $penceWrapper = $('#id_amount_pence-wrapper');

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
      var $detailsLink = $(e.target);
      var showTitle = $detailsLink.data('show-title');
      var loadingTitle = $detailsLink.data('loading-title');
      var hideTitle = $detailsLink.data('hide-title');
      var state = $detailsLink.data('credit-detail');

      function loadCreditDetails(html) {
        var $thisRow = $detailsLink.closest('tr').addClass('no-border');
        var $creditRow = $('<tr></tr>').addClass(creditRowClass).addClass($thisRow.attr('class'));
        var $creditCell = $('<td></td>');

        $creditRow.append(
          $creditCell.append($(html)).attr('colspan', 100)
        );
        $thisRow.after($creditRow);

        $detailsLink
          .text(hideTitle)
          .data('credit-detail', 'loaded')
          .attr('aria-expanded', 'true');
      }

      function removeCreditDetails() {
        var $thisRow = $detailsLink.closest('tr').removeClass('no-border');
        var $creditDetailsRow = $thisRow.next();

        if ($creditDetailsRow.hasClass(creditRowClass)) {
          $creditDetailsRow.remove();
        }
        $detailsLink
          .text(showTitle)
          .data('credit-detail', '')
          .attr('aria-expanded', 'false');
      }

      e.preventDefault();
      if (state === 'loaded') {
        // remove credit details

        removeCreditDetails();
      } else if (state !== 'loading') {
        // load credit details

        $detailsLink.text(loadingTitle);
        $detailsLink.data('credit-detail', 'loading');
        $.ajax({
          url: $detailsLink.data('ajax-url'),
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
