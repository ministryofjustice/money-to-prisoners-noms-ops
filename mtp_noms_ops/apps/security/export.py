import csv
import datetime
from decimal import Decimal
import io

from django.utils.translation import gettext_lazy as _


payment_methods = {
    'bank_transfer': _('Bank transfer'),
    'online': _('Debit card'),
}
credit_resolutions = {
    'pending': _('Pending'),
    'manual': _('Requires manual processing'),
    'credited': _('Credited'),
    'refunded': _('Refunded'),
}


def export_as_csv(credits):
    with io.StringIO() as out:
        writer = csv.writer(out)

        writer.writerow([
            'Prisoner name', 'Prisoner number', 'Prison',
            'Sender name', 'Payment method',
            'Bank transfer sort code', 'Bank transfer account', 'Bank transfer roll number',
            'Debit card number', 'Debit card expiry',
            'Amount', 'Date received',
            'Status', 'Date credited', 'NOMIS transaction',
        ])
        for credit in credits:
            cells = map(escape_csv_formula, [
                credit['prisoner_name'],
                credit['prisoner_number'],
                credit['prison_name'],
                credit['sender_name'],
                payment_methods.get(credit['source'], credit['source']),
                credit['sender_sort_code'],
                credit['sender_account_number'],
                credit['sender_roll_number'],
                '**** **** **** %s' % credit['card_number_last_digits'] if credit['card_number_last_digits'] else '',
                credit['card_expiry_date'],
                '£%.2f' % (Decimal(credit['amount']) / 100),
                credit['received_at'],
                credit_resolutions.get(credit['resolution'], credit['resolution']),
                credit['credited_at'],
                credit['nomis_transaction_id'],
            ])
            writer.writerow(list(cells))

        return out.getvalue()


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
