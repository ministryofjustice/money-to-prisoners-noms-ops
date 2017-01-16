import base64
import datetime

from django import template
from django.core.urlresolvers import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext

register = template.Library()


@register.filter(is_safe=True)
def currency(value):
    try:
        return '{:,.2f}'.format(value / 100)
    except TypeError:
        return ''


@register.filter
def parse_date_fields(credits):
    """
    MTP API responds with string date/time fields,
    this filter converts them to python objects
    """
    fields = ['received_at', 'credited_at', 'refunded_at']
    parsers = [parse_datetime, parse_date]

    def convert(credit):
        for field in fields:
            value = credit[field]
            if not value:
                continue
            for parser in parsers:
                try:
                    value = parser(value)
                    if isinstance(value, datetime.datetime):
                        value = timezone.localtime(value)
                    credit[field] = value
                    break
                except (ValueError, TypeError):
                    pass
        return credit

    return map(convert, credits)


@register.filter
def format_sort_code(sort_code):
    if sort_code and len(sort_code) == 6:
        return '%s-%s-%s' % (sort_code[0:2], sort_code[2:4], sort_code[4:6])
    return sort_code or ''


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
def clean_dict_values(dicts, key):
    for dic in dicts:
        if dic[key] is None:
            dic[key] = ''
    return dicts


@register.simple_tag
def get_credits_list_url(view, form, group, row):
    return reverse(view.credits_view) + '?' + \
           view.get_credits_row_query_string(form, group, row)


@register.simple_tag
def serialise_back_url(request):
    return base64.b64encode(request.get_full_path().encode('utf-8'))


@register.simple_tag
def unserialise_back_url(request):
    try:
        return base64.b64decode(request.GET['return_to']).decode('utf-8')
    except (KeyError, ValueError):
        return reverse('dashboard')


@register.simple_tag(takes_context=True)
def credit_group_title_for_sender(context):
    request = context.get('request')
    if not request:
        return ''

    sender_name = request.GET.get('sender_name')
    if sender_name:
        credit_group_title = gettext('Sender %(sender_name)s') % {'sender_name': sender_name}
    else:
        credit_group_title = gettext('Unknown sender')

    sender_sort_code = request.GET.get('sender_sort_code', '')
    if sender_sort_code:
        sender_sort_code = format_sort_code(sender_sort_code)
    sender_account_number = request.GET.get('sender_account_number', '')
    sender_roll_number = request.GET.get('sender_roll_number', '')
    if sender_account_number and sender_roll_number:
        sender_account_number = '%s/%s' % (sender_account_number, sender_roll_number)
    sender_account = ('%s %s' % (sender_sort_code, sender_account_number)).strip()
    if sender_account:
        credit_group_title = escape(credit_group_title)
        sender_account = escape(sender_account)
        credit_group_title = mark_safe('%s<br>\n<small>%s</small>' % (credit_group_title, sender_account))

    return credit_group_title


@register.filter
def list_prison_names(prisons):
    return ', '.join((prison['name'] for prison in prisons))
