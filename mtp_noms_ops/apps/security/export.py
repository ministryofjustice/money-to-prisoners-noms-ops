import csv
import datetime
import re

from django.http import HttpResponse
from django.utils.translation import gettext, gettext_lazy as _

from security.templatetags.security import currency, format_card_number, format_sort_code, format_resolution

payment_methods = {
    'bank_transfer': _('Bank transfer'),
    'online': _('Debit card'),
}


class CreditCsvResponse(HttpResponse):
    def __init__(self, object_list, attachment_name='export.csv', **kwargs):
        kwargs.setdefault('content_type', 'text/csv')
        super().__init__(**kwargs)
        self['Content-Disposition'] = 'attachment; filename="%s"' % attachment_name
        writer = csv.writer(self)
        write_header(writer)
        write_credits(writer, object_list)


def write_header(writer):
    writer.writerow([
        gettext('Prisoner name'), gettext('Prisoner number'), gettext('Prison'),
        gettext('Sender name'), gettext('Payment method'),
        gettext('Bank transfer sort code'), gettext('Bank transfer account'), gettext('Bank transfer roll number'),
        gettext('Debit card number'), gettext('Debit card expiry'), gettext('Address'),
        gettext('Amount'), gettext('Date received'),
        gettext('Credited status'), gettext('Date credited'), gettext('NOMIS ID'),
        gettext('IP'),
    ])


def write_credits(writer, object_list):
    for credit in object_list:
        cells = [
            credit['prisoner_name'],
            credit['prisoner_number'],
            credit['prison_name'],
            credit['sender_name'],
            payment_methods.get(credit['source'], credit['source']),
            format_sort_code(credit['sender_sort_code']) if credit['sender_sort_code'] else '',
            credit['sender_account_number'],
            credit['sender_roll_number'],
            format_card_number(credit['card_number_last_digits']) if credit['card_number_last_digits'] else '',
            credit['card_expiry_date'],
            address_for_csv(credit['billing_address']),
            currency(credit['amount']),
            credit['received_at'],
            format_resolution(credit['resolution']),
            credit['credited_at'],
            credit['nomis_transaction_id'],
            credit['ip_address'],
        ]
        writer.writerow(list(map(escape_csv_formula, cells)))


def escape_csv_formula(value):
    """
    Escapes formulae (strings that start with =) to prevent
    spreadsheet software vulnerabilities being exploited
    :param value: the value being added to a CSV cell
    """
    if isinstance(value, str) and value.startswith('='):
        return "'" + value
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, datetime.date):
        return value.strftime('%Y-%m-%d')
    return value


def address_for_csv(address):
    if not address:
        return ''
    whitespace = re.compile(r'\s+')
    keys = ('line1', 'line2', 'city', 'postcode', 'country')
    lines = (whitespace.sub(' ', address[key]).strip() for key in keys if address.get(key))
    return ', '.join(lines)
