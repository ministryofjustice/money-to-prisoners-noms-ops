import logging

from django import template
from django.core.urlresolvers import reverse
from django.utils.encoding import force_text
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
def append(prefix, suffix):
    if prefix is None:
        prefix = ''
    if suffix is None:
        suffix = ''
    return force_text(prefix) + force_text(suffix)


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
    return ', '.join((prison['name'] for prison in prisons))


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
