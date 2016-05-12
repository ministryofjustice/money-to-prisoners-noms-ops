import base64
import datetime

from django import template
from django.core.urlresolvers import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

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
        return base64.b64decode(request.GET['back']).decode('utf-8')
    except (KeyError, ValueError):
        return reverse('security_dashboard')
