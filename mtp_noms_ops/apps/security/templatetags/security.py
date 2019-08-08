import re
import logging

from django import template
from django.core.urlresolvers import reverse
from django.utils.html import escape
from django.utils.http import urlencode
from django.utils.safestring import mark_safe

from security.models import (
    credit_sources, credit_resolutions,
    disbursement_methods, disbursement_actions, disbursement_resolutions,
)

logger = logging.getLogger('mtp')
register = template.Library()


BANK_TRANSFER_SENDER_KEYS = [
    'sender_name', 'sender_sort_code', 'sender_account_number', 'sender_roll_number',
]
DEBIT_CARD_SENDER_KEYS = [
    'card_number_last_digits', 'card_expiry_date', 'postcode',
]


@register.filter
def currency(pence_value):
    try:
        return '£{:,.2f}'.format(pence_value / 100)
    except TypeError:
        return pence_value


@register.filter
def pence(pence_value):
    try:
        assert isinstance(pence_value, int)
        if pence_value >= 100:
            return currency(pence_value)
        return '%dp' % pence_value
    except AssertionError:
        return pence_value


@register.filter
def format_sort_code(sort_code):
    if sort_code and len(sort_code) == 6:
        return '%s-%s-%s' % (sort_code[0:2], sort_code[2:4], sort_code[4:6])
    return sort_code or '—'


@register.filter
def format_card_number(card_number_last_digits):
    return '**** **** **** %s' % (card_number_last_digits or '****')


@register.filter
def credit_source(source_key):
    return credit_sources.get(source_key, source_key)


@register.filter
def format_resolution(resolution):
    return credit_resolutions.get(resolution, resolution)


@register.filter
def list_prison_names(prisons):
    """
    Returns prison names in `prisons` as a comma separated string.
    """
    return ', '.join((prison['name'] for prison in prisons))


@register.simple_tag
def get_split_prison_names(prisons, split_at=3):
    """
    Same as `list_prison_names` but only including the first `split_at` prisons.

    Returns a dict with
        prison_names: first `split_at` prison names in `prisons` as a comma separated string
        total_remaining: number of remaining prisons that were not included in `prison_names`

    :param prisons: list of dicts with prison data
    :split_at: number of prisons to be included in the prison_names join.
    """
    return {
        'prison_names': list_prison_names(prisons[:split_at]),
        'total_remaining': len(prisons[split_at:]),
    }


@register.filter
def query_string_with_additional_parameter(form, param):
    data = form.get_query_data(allow_parameter_manipulation=False)
    data[param] = 1
    return urlencode(data, doseq=True)


def get_profile_search_url(credit, keys, url, redirect_on_single=True):
    params = urlencode((key, credit[key]) for key in keys if key in credit and credit[key])
    if redirect_on_single:
        return url + '?redirect-on-single&' + params
    return url + '?' + params


def get_sender_keys(credit):
    keys = {'sender_name'}
    if credit['source'] == 'bank_transfer':
        keys.update(BANK_TRANSFER_SENDER_KEYS)
    elif credit['source'] == 'online':
        keys.update(DEBIT_CARD_SENDER_KEYS)
    else:
        logger.error('Credit %s had an unknown source' % credit.get('id'))
    return keys


@register.filter
def sender_profile_search_url(credit, redirect_on_single=True):
    """
    Given an API credit response object, returns the URL for searching this sender
    """
    sender_id = credit.get('sender_profile')
    if sender_id:
        return reverse('security:sender_detail', kwargs={'sender_id': sender_id})
    keys = list(get_sender_keys(credit))
    return get_profile_search_url(credit, keys, reverse('security:sender_list'),
                                  redirect_on_single=redirect_on_single)


@register.filter
def credit_sender_identifiable(credit):
    keys = get_sender_keys(credit)
    return any([credit[key] for key in keys - {'postcode'}])


@register.filter
def sender_identifiable(sender):
    if sender.get('bank_transfer_details'):
        return any([sender['bank_transfer_details'][0][key] for key in BANK_TRANSFER_SENDER_KEYS])
    elif sender.get('debit_card_details'):
        return any([sender['debit_card_details'][0][key] for key in DEBIT_CARD_SENDER_KEYS])
    else:
        return False


@register.filter
def prisoner_profile_search_url(credit, redirect_on_single=True):
    """
    Given an API credit response object, returns the URL for searching this prisoner
    """
    prisoner_id = credit.get('prisoner_profile')
    if prisoner_id:
        return reverse('security:prisoner_detail', kwargs={'prisoner_id': prisoner_id})
    return get_profile_search_url(credit, ['prisoner_number'], reverse('security:prisoner_list'),
                                  redirect_on_single=redirect_on_single)


@register.filter
def format_address(obj):
    if obj:
        if 'address_line1' in obj:
            # disbursement object
            keys = ('address_line1', 'address_line2', 'city', 'postcode', 'country')
        else:
            # credit's address sub-object
            keys = ('line1', 'line2', 'city', 'postcode', 'country')
        return mark_safe('<br/>'.join(
            escape(obj[key])
            for key in keys
            if obj.get(key)
        ))


@register.filter
def disbursement_method(method_key):
    return disbursement_methods.get(method_key, method_key)


@register.filter
def format_disbursement_action(value):
    return disbursement_actions.get(value, value)


@register.filter
def format_disbursement_resolution(value):
    return disbursement_resolutions.get(value, value)


@register.filter
def find_rejection_reason(comment_set):
    for comment in filter(lambda comment: comment['category'] == 'reject', comment_set):
        return comment['comment']
    return ''


def _build_search_terms_re(context):
    """
    Constructs the compiled regex pattern from the search term in the context.
    It returns None if not on the search results page, if the form is not in the context or the
    search term can't be found.
    The search term is automatically obtained from the simple_form field of the form in the context.

    The value used in the regex pattern is html and regex escaped which means that you need to escape
    the test string as well when using it.
    """
    in_search_results = context.get('is_search_results', False)
    if not in_search_results:
        return None

    form = context.get('form')
    if not form:
        return None

    search_term = form.cleaned_data.get('simple_search')

    if not search_term:
        return None

    search_terms = [
        re.escape(
            escape(term),
        )
        for term in search_term.split()
    ]
    return re.compile(f'({"|".join(search_terms)})', re.I)


def _get_cached_search_terms_re(context):
    """
    Returns the cached seach_terms_re to be used.
    """
    if '_search_terms_re' not in context:
        context['_search_terms_re'] = _build_search_terms_re(context)
    return context['_search_terms_re']


@register.simple_tag(takes_context=True)
def setup_highlight(context):
    """
    Template tag that can be used to optimise the highlight logic by caching the compiled reex pattern.
    """
    # warm up cache
    _ = _get_cached_search_terms_re(context)
    return ''


@register.simple_tag(takes_context=True)
def search_highlight(context, value, default=''):
    """
    Wraps all search term words contained in 'value' with a span with class 'mtp-search-highlight'.
    The search term is automatically obtained from the simple_form field of the form in the context.
    It only works on the search results page.
    It returns 'default' if 'value' is emnpty.
    """
    if not value:
        return default

    escaped_value = escape(value)
    search_terms_re = _get_cached_search_terms_re(context)
    if search_terms_re:
        return mark_safe(
            search_terms_re.sub(r'<span class="mtp-search-highlight">\1</span>', escaped_value),
        )
    return value


@register.simple_tag(takes_context=True)
def extract_best_match(context, items):
    """
    Takes a list and returns a dict with:
    - 'item': best item in the list that matches the search term
    - 'total_remaining': total number of other items in the list

    The best match equals a random item in the list if the user is not not on the
    search results page or if there's no match in the list.
    """
    item_list = items or []
    best_match = None

    search_terms_re = _get_cached_search_terms_re(context)

    if search_terms_re:
        best_match = next(
            (
                item
                for item in item_list
                if search_terms_re.search(escape(item))
            ),
            None,
        )

    if not best_match and item_list:
        best_match = item_list[0]

    return {
        'item': best_match,
        'total_remaining': max(len(item_list)-1, 0),
    }
