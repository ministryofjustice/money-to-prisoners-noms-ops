import logging

from django import template
from django.core.urlresolvers import reverse
from django.forms.utils import flatatt
from django.utils.html import format_html_join
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.utils.translation import gettext

logger = logging.getLogger('mtp')
register = template.Library()


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
def format_resolution(resolution):
    if resolution == 'initial':
        return gettext('Initial')
    if resolution == 'pending':
        return gettext('Pending')
    if resolution == 'credited':
        return gettext('Credited')
    if resolution == 'refunded':
        return gettext('Refunded')
    return resolution


@register.filter
def list_prison_names(prisons):
    return ', '.join((prison['name'] for prison in prisons))


@register.filter
def ordering_classes(form, ordering):
    current_ordering = form.cleaned_data.get('ordering')
    if current_ordering == ordering:
        return 'mtp-results-ordering mtp-results-ordering--asc'
    if current_ordering == '-%s' % ordering:
        return 'mtp-results-ordering mtp-results-ordering--desc'
    return 'mtp-results-ordering'


@register.inclusion_tag('security/includes/result-ordering-for-screenreader.html')
def describe_ordering_for_screenreader(form, ordering):
    current_ordering = form.cleaned_data.get('ordering')
    if current_ordering == ordering:
        ordering = 'ascending'
    elif current_ordering == '-%s' % ordering:
        ordering = 'descending'
    else:
        ordering = None
    return {'ordering': ordering}


@register.filter
def query_string_with_reversed_ordering(form, ordering):
    data = form.get_query_data(allow_parameter_manipulation=False)
    current_ordering = data.get('ordering')
    if current_ordering == ordering:
        ordering = '-%s' % ordering
    data['ordering'] = ordering
    return urlencode(data, doseq=True)


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


@register.filter
def sender_profile_search_url(credit, redirect_on_single=True):
    """
    Given an API credit response object, returns the URL for searching this sender
    """
    sender_id = credit.get('sender_profile')
    if sender_id:
        return reverse('security:sender_detail', kwargs={'sender_id': sender_id})
    keys = ['sender_name']
    if credit['source'] == 'bank_transfer':
        keys.extend(['sender_sort_code', 'sender_account_number', 'sender_roll_number'])
    elif credit['source'] == 'online':
        keys.extend(['card_number_last_digits', 'card_expiry_date'])
    else:
        logger.error('Credit %s had an unknown source' % credit.get('id'))
    return get_profile_search_url(credit, keys, reverse('security:sender_list'),
                                  redirect_on_single=redirect_on_single)


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


@register.simple_tag
def tab_aria_atts(field):
    panel_id = 'mtp-tabpanel-%s' % field
    return flatatt({
        'id': 'mtp-tab-%s' % field,
        'href': '#%s' % panel_id,
        'role': 'tab',
        'aria-controls': panel_id,
        'aria-flowto': panel_id,
    })


@register.simple_tag
def panel_aria_atts(field):
    return flatatt({
        'id': 'mtp-tabpanel-%s' % field,
        'role': 'tabpanel',
        'aria-labelledby': 'mtp-tab-%s' % field,
    })


@register.filter
def format_address(address):
    lines = [(address[key],) for key in ('line1', 'line2', 'city', 'postcode', 'country') if address.get(key)]
    return format_html_join(mark_safe('<br />'), '{}', lines)
