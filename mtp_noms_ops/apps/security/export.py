import datetime
import re

from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from mtp_common.utils import format_currency
from openpyxl import Workbook

from security.models import credit_sources, disbursement_methods
from security.templatetags.security import (
    format_card_number, format_sort_code,
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
        serialiser = ObjectListSerialiser.serialiser_for(object_type)
        workbook = serialiser.make_workbook(object_list)
        workbook.save(self)


class ObjectListSerialiser:
    serialisers = {}
    headers = []

    def __init_subclass__(cls, object_type):
        cls.serialisers[object_type] = cls

    @classmethod
    def serialiser_for(cls, object_type):
        try:
            return cls.serialisers[object_type]()
        except KeyError:
            raise NotImplementedError(f'Cannot export {object_type}')

    def make_workbook(self, object_list):
        workbook = Workbook(write_only=True)
        worksheet = workbook.create_sheet()
        worksheet.append(self.headers)
        for record in object_list:
            serialised_record = self.serialise(record)
            worksheet.append([
                escape_formulae(serialised_record.get(field))
                for field in self.headers
            ])
        return workbook

    def serialise(self, record):
        raise NotImplementedError


class CreditListSerialiser(ObjectListSerialiser, object_type='credits'):
    headers = [
        'Internal ID',
        'Date started', 'Date received', 'Date credited',
        'Amount',
        'Prisoner number', 'Prisoner name', 'Prison',
        'Sender name', 'Payment method',
        'Bank transfer sort code', 'Bank transfer account', 'Bank transfer roll number',
        'Debit card number', 'Debit card expiry', 'Debit card billing address',
        'Sender email', 'Sender IP address',
        'Status',
        'NOMIS transaction',
    ]

    def serialise(self, record):
        return {
            'Internal ID': record['id'],
            'Date started': record['started_at'],
            'Date received': (
                record['received_at'].strftime('%Y-%m-%d')
                if record['source'] == 'bank_transfer' else record['received_at']
            ),
            'Date credited': record['credited_at'],
            'Amount': format_currency(record['amount']),
            'Prisoner number': record['prisoner_number'],
            'Prisoner name': record['prisoner_name'],
            'Prison': record['prison_name'],
            'Sender name': record['sender_name'],
            'Payment method': str(credit_sources.get(record['source'], record['source'])),
            'Bank transfer sort code': (
                format_sort_code(record['sender_sort_code']) if record['sender_sort_code'] else None
            ),
            'Bank transfer account': record['sender_account_number'],
            'Bank transfer roll number': record['sender_roll_number'],
            'Debit card number': (
                f'{record["card_number_first_digits"] or "******"}******{record["card_number_last_digits"]}'
                if record['card_number_last_digits']
                else None
            ),
            'Debit card expiry': record['card_expiry_date'],
            'Debit card billing address': credit_address_for_export(record['billing_address']),
            'Sender email': record['sender_email'],
            'Sender IP address': record['ip_address'],
            'Status': str(format_resolution(record['resolution'])),
            'NOMIS transaction': record['nomis_transaction_id'],
        }


class DisbursementListSerialiser(ObjectListSerialiser, object_type='disbursements'):
    headers = [
        'Internal ID',
        'Date entered', 'Date confirmed', 'Date sent',
        'Amount',
        'Prisoner number', 'Prisoner name', 'Prison',
        'Recipient name', 'Payment method',
        'Bank transfer sort code', 'Bank transfer account', 'Bank transfer roll number',
        'Recipient address', 'Recipient email',
        'Status',
        'NOMIS transaction', 'SOP invoice number',
    ]

    def serialise(self, record):
        last_action_dates = {
            log_item['action']: parse_datetime(log_item['created'])
            for log_item in record['log_set']
        }
        return {
            'Internal ID': record['id'],
            'Date entered': record['created'],
            'Date confirmed': last_action_dates.get('confirmed', ''),
            'Date sent': last_action_dates.get('sent', ''),
            'Amount': format_currency(record['amount']),
            'Prisoner number': record['prisoner_number'],
            'Prisoner name': record['prisoner_name'],
            'Prison': record['prison_name'],
            'Recipient name': f'{record["recipient_first_name"]} {record["recipient_last_name"]}'.strip(),
            'Payment method': str(disbursement_methods.get(record['method'], record['method'])),
            'Bank transfer sort code': (
                format_sort_code(record['sort_code']) if record['sort_code'] else ''
            ),
            'Bank transfer account': record['account_number'],
            'Bank transfer roll number': record['roll_number'],
            'Recipient address': disbursement_address_for_export(record),
            'Recipient email': record['recipient_email'],
            'Status': str(format_disbursement_resolution(record['resolution'])),
            'NOMIS transaction': record['nomis_transaction_id'],
            'SOP invoice number': record['invoice_number'],
        }


class SenderListSerialiser(ObjectListSerialiser, object_type='senders'):
    headers = [
        'Sender name', 'Payment method',
        'Credits sent', 'Total amount sent',
        'Prisoners sent to', 'Prisons sent to',
        'Bank transfer sort code', 'Bank transfer account', 'Bank transfer roll number',
        'Debit card number', 'Debit card expiry', 'Debit card postcode',
        'Other cardholder names', 'Cardholder emails',
    ]

    def serialise(self, record):
        serialised_record = {
            'Credits sent': record['credit_count'],
            'Total amount sent': format_currency(record['credit_total']),
            'Prisoners sent to': record['prisoner_count'],
            'Prisons sent to': record['prison_count'],
        }

        if record.get('bank_transfer_details'):
            bank_transfer = record['bank_transfer_details'][0]
            return {
                **serialised_record,
                'Sender name': bank_transfer['sender_name'],
                'Payment method': 'Bank transfer',
                'Bank transfer sort code': format_sort_code(bank_transfer['sender_sort_code']),
                'Bank transfer account': bank_transfer['sender_account_number'],
                'Bank transfer roll number': bank_transfer['sender_roll_number'],
            }

        if record.get('debit_card_details'):
            debit_card = record['debit_card_details'][0]
            try:
                sender_name = debit_card['cardholder_names'][0]
            except IndexError:
                sender_name = 'Unknown'
            other_sender_names = NameSet(debit_card['cardholder_names'])
            if sender_name in other_sender_names:
                other_sender_names.remove(sender_name)
            return {
                **serialised_record,
                'Sender name': sender_name,
                'Payment method': 'Debit card',
                'Debit card number': format_card_number(debit_card),
                'Debit card expiry': debit_card['card_expiry_date'],
                'Debit card postcode': debit_card['postcode'] or 'Unknown',
                'Other cardholder names': ', '.join(other_sender_names),
                'Cardholder emails': ', '.join(EmailSet(debit_card['sender_emails'])),
            }

        return {
            **serialised_record,
            'Sender name': '(Unknown)',
            'Payment method': '(Unknown)',
        }


class PrisonerListSerialiser(ObjectListSerialiser, object_type='prisoners'):
    headers = [
        'Prisoner number',
        'Prisoner name',
        'Date of birth',
        'Credits received',
        'Total amount received',
        'Payment sources',
        'Disbursements sent',
        'Total amount sent',
        'Recipients',
        'Current prison',
        'All known prisons',
        'Names given by senders',
    ]

    def serialise(self, record):
        if record['current_prison']:
            current_prison = record['current_prison']['name']
        else:
            current_prison = 'Not in a public prison'
        provided_names = NameSet(record['provided_names'])
        return {
            'Prisoner number': record['prisoner_number'],
            'Prisoner name': record['prisoner_name'],
            'Date of birth': record['prisoner_dob'],
            'Credits received': record['credit_count'],
            'Total amount received': format_currency(record['credit_total']),
            'Payment sources': record['sender_count'],
            'Disbursements sent': record['disbursement_count'],
            'Total amount sent': format_currency(record['disbursement_total']),
            'Recipients': record['recipient_count'],
            'Current prison': current_prison,
            'All known prisons': list_prison_names(record['prisons']),
            'Names given by senders': ', '.join(provided_names),
        }


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
