import datetime
import itertools
import logging

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from mtp_common.nomis import get_transaction_history
from requests.exceptions import RequestException

from security.models import PrisonList

logger = logging.getLogger('mtp')

oldest_transaction_date = datetime.date(2016, 3, 1)  # brixton pilot started 2016-03-02
page_of_transactions = datetime.timedelta(days=120)


def as_credit(prison_names, prisoner_number, prison):
    def mapper(transaction):
        credit = {
            'source': 'post',
            'nomis_transaction': transaction,
            'prisoner_number': prisoner_number,
            'prison': prison,
            'prison_name': prison_names.get(prison, _('Unknown')),
        }
        try:
            # arbitrarily state that money by post is received at 8am
            credit['received_at'] = timezone.make_aware(
                datetime.datetime(*map(int, transaction['date'].split('-')),
                                  hour=8)
            )
        except (KeyError, ValueError, TypeError):
            logger.warning('Cannot parse date for NOMIS transaction; %s at %s: %s' % (
                prisoner_number, prison, transaction.get('id'),
            ))
            return None
        try:
            credit['amount'] = int(transaction['amount'])
        except (KeyError, ValueError):
            logger.warning('Cannot parse amount for NOMIS transaction; %s at %s: %s' % (
                prisoner_number, prison, transaction.get('id'),
            ))
            return None
        return credit

    return mapper


def get_money_by_post_at_prison(prison_names, prisoner_number, prison,
                                from_date, to_date=None, paginate_backwards=False):
    try:
        parameters = {
            'prison_id': prison,
            'prisoner_number': prisoner_number,
            'account_code': 'cash',
            'from_date': from_date,
        }
        if to_date:
            parameters['to_date'] = to_date
        # get transaction history
        transactions = get_transaction_history(**parameters).get('transactions', [])
        while paginate_backwards:
            # paginate backwards in time until the earliest allowed date
            if parameters['from_date'] <= oldest_transaction_date:
                break
            parameters['to_date'] = parameters['from_date'] - datetime.timedelta(days=1)
            parameters['from_date'] = parameters['to_date'] - page_of_transactions
            transactions += get_transaction_history(**parameters).get('transactions', [])
    except RequestException:
        logger.exception('Could not load transaction history for %s at %s' % (prisoner_number, prison))
        return []

    # filter out only money by post
    transactions = filter(lambda t: t.get('type', {}).get('code') == 'POST', transactions)

    # convert to credit shape and add known additional info
    return filter(None, map(as_credit(prison_names, prisoner_number, prison), transactions))


def merge_money_by_post(form, prisoner):
    """
    Looks up a prisoner's money-by-post transactions and merges them into form's credit list.
    Merged credits can be sorted by received_at or amount only.
    NOMIS can currently filter only by date so sometimes all transactions must be loaded
    For consistent ordering and pagination, money-by-post transactions are dropped off the end of non-final pages
    so that they aren't duplicated on the next page.
    If ordering by amount, need to peek at preceeding page's last MTP credit to determine if transaction should appear
    on this page at all.
    """
    page_count = form.page_count
    page = form.cleaned_data.get('page', 0)
    object_list = form.cleaned_data.get('object_list')
    prisoner_number = prisoner.get('prisoner_number')
    prisons = [prisoner.get('current_prison', {}).get('nomis_id')] + \
              [prison.get('nomis_id') for prison in prisoner.get('prisons', [])]
    prisons = set(filter(None, prisons))
    if not (object_list and page and prisoner_number and prisons):
        # no credits or missing inputs (e.g. form not valid)
        return

    # determine ordering and money-by-post filters
    ordering = form.cleaned_data.get('ordering', '')
    sorted_reverse = ordering.startswith('-')
    if sorted_reverse:
        ordering = ordering[1:]
    on_first_page = page == 1
    on_last_page = page == page_count
    continues_before_start_of_page = sorted_reverse and not on_first_page
    continues_after_end_of_page = not sorted_reverse and not on_last_page
    money_by_post_filter = None
    if ordering == 'received_at':
        first_date_of_page = object_list[0]['received_at'].date()
        last_date_of_page = object_list[-1]['received_at'].date()
        if sorted_reverse:
            from_date, to_date = last_date_of_page, first_date_of_page
            paginate_backwards = on_last_page
        else:
            from_date, to_date = first_date_of_page, last_date_of_page
            paginate_backwards = on_first_page
    else:
        from_date = datetime.date.today() - page_of_transactions
        to_date = None
        paginate_backwards = True
        preceeding_credit = peek_preceeding_credit(form, sorted_reverse, on_first_page, on_last_page)
        if preceeding_credit:
            if sorted_reverse:
                def money_by_post_filter(transaction):
                    return transaction[ordering] >= preceeding_credit[ordering]
            else:
                def money_by_post_filter(transaction):
                    return transaction[ordering] <= preceeding_credit[ordering]

        if ordering != 'amount':
            logger.error('Ordering money-by-post by %s is not implemented' % ordering)
            return

    # get money-by-post for all prisoner's prisons
    prison_list = PrisonList(form.client)
    prison_names = dict(prison_list.prison_choices)
    money_by_post = itertools.chain.from_iterable(
        get_money_by_post_at_prison(prison_names, prisoner_number, prison,
                                    from_date=from_date, to_date=to_date, paginate_backwards=paginate_backwards)
        for prison in prisons
    )
    money_by_post = list(filter(money_by_post_filter, money_by_post))
    if sorted_reverse:
        # for consistent ordering of 'equal' transactions
        money_by_post = list(reversed(money_by_post))

    # merge credits
    merged_object_list = sorted(object_list + money_by_post,
                                key=lambda credit: credit[ordering],
                                reverse=sorted_reverse)
    # drop money-by-post off the highest end of the page to not repeat them overleaf
    merged_object_list = prevent_money_by_post_duplicates(merged_object_list,
                                                          continues_before_start_of_page,
                                                          continues_after_end_of_page)

    form.cleaned_data['object_list'] = merged_object_list


def peek_preceeding_credit(form, sorted_reverse, on_first_page, on_last_page):
    data = form.cleaned_data.copy()
    data.pop('object', None)
    data.pop('object_list', None)
    if not sorted_reverse and not on_first_page:
        # peek previous page's last
        data['page'] -= 1
        index = -1
    elif sorted_reverse and not on_last_page:
        # peek next page's first
        data['page'] += 1
        index = 0
    else:
        return
    new_form = form.__class__(request=form.request, object_id=form.object_id, data=data)
    if new_form.is_valid():
        object_list = new_form.cleaned_data['object_list']
        return object_list[index]


def prevent_money_by_post_duplicates(merged_object_list, continues_before_start_of_page, continues_after_end_of_page):
    if continues_before_start_of_page:
        # drop from start
        for index, item in enumerate(merged_object_list):
            if item['source'] != 'post':
                merged_object_list = merged_object_list[index:]
                break
    elif continues_after_end_of_page:
        # drop from end
        for index, item in enumerate(reversed(merged_object_list)):
            if item['source'] != 'post':
                merged_object_list = merged_object_list[:len(merged_object_list) - index]
                break
    return merged_object_list
