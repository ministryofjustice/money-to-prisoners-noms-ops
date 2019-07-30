import datetime
import re

from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext
from openpyxl import Workbook

from security.models import credit_sources, disbursement_methods
from security.templatetags.security import (
    currency, format_card_number, format_sort_code,
    format_resolution, format_disbursement_resolution,
    list_prison_names,
)
from security.utils import EmailSet, NameSet


class ObjectListXlsxResponse(HttpResponse):
    def __init__(self, object_list, object_type, attachment_name='export.xlsx', **kwargs):
        kwargs.setdefault(
            'content_type',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        super().__init__(**kwargs)
        self['Content-Disposition'] = 'attachment; filename="%s"' % attachment_name
        wb = Workbook(write_only=True)
        write_objects(wb, object_type, object_list)
        wb.save(self)


def write_objects(workbook, object_type, object_list):
    if object_type == 'credits':
        rows = credit_row_generator(object_list)
    elif object_type == 'senders':
        rows = sender_row_generator(object_list)
    elif object_type == 'prisoners':
        rows = prisoner_row_generator(object_list)
    elif object_type == 'disbursements':
        rows = disbursement_row_generator(object_list)
    else:
        raise ValueError
    worksheet = workbook.create_sheet()
    for row in rows:
        worksheet.append([escape_formulae(cell) for cell in row])


def credit_row_generator(object_list):
    yield [
        gettext('Prisoner name'), gettext('Prisoner number'), gettext('Prison'),
        gettext('Sender name'), gettext('Payment method'),
        gettext('Bank transfer sort code'), gettext('Bank transfer account'), gettext('Bank transfer roll number'),
        gettext('Debit card number'), gettext('Debit card expiry'), gettext('Address'),
        gettext('Amount'), gettext('Date received'),
        gettext('Credited status'), gettext('Date credited'), gettext('NOMIS ID'),
        gettext('IP'), gettext('Email'),
    ]
    for credit in object_list:
        yield [
            credit['prisoner_name'],
            credit['prisoner_number'],
            credit['prison_name'],
            credit['sender_name'],
            str(credit_sources.get(credit['source'], credit['source'])),
            format_sort_code(credit['sender_sort_code']) if credit['sender_sort_code'] else '',
            credit['sender_account_number'],
            credit['sender_roll_number'],
            format_card_number(credit['card_number_last_digits']) if credit['card_number_last_digits'] else '',
            credit['card_expiry_date'],
            credit_address_for_export(credit['billing_address']),
            currency(credit['amount']),
            credit['received_at'],
            str(format_resolution(credit['resolution'])),
            credit['credited_at'],
            credit['nomis_transaction_id'],
            credit['ip_address'],
            credit['sender_email'],
        ]


def sender_row_generator(object_list):
    yield [
        gettext('Sender name'), gettext('Payment source'),
        gettext('Credits sent'), gettext('Total amount sent'),
        gettext('Prisoners sent to'), gettext('Prisons sent to'),
        gettext('Bank transfer sort code'), gettext('Bank transfer account'), gettext('Bank transfer roll number'),
        gettext('Debit card number'), gettext('Debit card expiry'), gettext('Debit card postcode'),
        gettext('Other cardholder names'), gettext('Cardholder emails'),
    ]
    for sender in object_list:
        if sender['bank_transfer_details']:
            payment_source = gettext('Bank transfer')
            bank_transfer = sender['bank_transfer_details'][0]
            sender_name = bank_transfer['sender_name']
            bank_transfer = [format_sort_code(bank_transfer['sender_sort_code']),
                             bank_transfer['sender_account_number'],
                             bank_transfer['sender_roll_number']]
            debit_card = ['', '', '', '', '']
        elif sender['debit_card_details']:
            payment_source = gettext('Debit card')
            bank_transfer = ['', '', '']
            debit_card = sender['debit_card_details'][0]
            sender_name = debit_card['cardholder_names'][0]
            other_sender_names = NameSet(debit_card['cardholder_names'])
            if sender_name in other_sender_names:
                other_sender_names.remove(sender_name)
            debit_card = [format_card_number(debit_card['card_number_last_digits']),
                          debit_card['card_expiry_date'],
                          debit_card['postcode'] or gettext('Unknown'),
                          ', '.join(other_sender_names),
                          ', '.join(EmailSet(debit_card['sender_emails']))]
        else:
            continue
        yield [
            sender_name, payment_source,
            sender['credit_count'], currency(sender['credit_total']),
            sender['prisoner_count'], sender['prison_count'],
        ] + bank_transfer + debit_card


def prisoner_row_generator(object_list):
    yield [
        gettext('Prisoner number'),
        gettext('Prisoner name'),
        gettext('Date of birth'),
        gettext('Credits received'),
        gettext('Total amount received'),
        gettext('Payment sources'),
        gettext('Current prison'),
        gettext('Prisons where received credits'),
        gettext('Names given by senders'),
        gettext('Disbursements sent'),
        gettext('Total amount sent'),
        gettext('Recipients'),
    ]
    for prisoner in object_list:
        if prisoner['current_prison']:
            current_prison = prisoner['current_prison']['name']
        else:
            current_prison = gettext('Not in a public prison')
        provided_names = NameSet(prisoner['provided_names'])
        yield [
            prisoner['prisoner_number'],
            prisoner['prisoner_name'],
            prisoner['prisoner_dob'],
            prisoner['credit_count'],
            currency(prisoner['credit_total']),
            prisoner['sender_count'],
            current_prison,
            list_prison_names(prisoner['prisons']),
            ', '.join(provided_names),
            prisoner['disbursement_count'],
            currency(prisoner['disbursement_total']),
            prisoner['recipient_count'],
        ]


def disbursement_row_generator(object_list):
    yield [
        gettext('Prisoner name'), gettext('Prisoner number'), gettext('Prison'),
        gettext('Recipient first name'), gettext('Recipient last name'), gettext('Payment method'),
        gettext('Address'), gettext('Recipient email'),
        gettext('Bank transfer sort code'), gettext('Bank transfer account'), gettext('Bank transfer roll number'),
        gettext('Amount'), gettext('Status'),
        gettext('Date entered'), gettext('Date confirmed'),  gettext('Date sent'),
        gettext('NOMIS ID'),
    ]
    for disbursement in object_list:
        last_action_dates = {
            log_item['action']: parse_datetime(log_item['created'])
            for log_item in disbursement['log_set']
        }
        yield [
            disbursement['prisoner_name'],
            disbursement['prisoner_number'],
            disbursement['prison_name'],
            disbursement['recipient_first_name'], disbursement['recipient_last_name'],
            str(disbursement_methods.get(disbursement['method'], disbursement['method'])),
            disbursement_address_for_export(disbursement),
            disbursement['recipient_email'],
            format_sort_code(disbursement['sort_code']) if disbursement['sort_code'] else '',
            disbursement['account_number'],
            disbursement['roll_number'],
            currency(disbursement['amount']),
            str(format_disbursement_resolution(disbursement['resolution'])),
            disbursement['created'],
            last_action_dates.get('confirmed', ''),
            last_action_dates.get('sent', ''),
            disbursement['nomis_transaction_id'],
        ]


def escape_formulae(value):
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


def credit_address_for_export(address):
    if not address:
        return ''
    whitespace = re.compile(r'\s+')
    keys = ('line1', 'line2', 'city', 'postcode', 'country')
    lines = (whitespace.sub(' ', address[key]).strip() for key in keys if address.get(key))
    return ', '.join(lines)


def disbursement_address_for_export(disbursement):
    whitespace = re.compile(r'\s+')
    keys = ('address_line1', 'address_line2', 'city', 'postcode', 'country')
    lines = (whitespace.sub(' ', disbursement[key]).strip() for key in keys if disbursement.get(key))
    return ', '.join(lines)
