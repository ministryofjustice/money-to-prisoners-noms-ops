import csv
import datetime
from decimal import Decimal
import io


def export_as_csv(credits):
    with io.StringIO() as out:
        writer = csv.writer(out)

        writer.writerow([
            'prisoner_name', 'prisoner_number', 'prison', 'sender_name',
            'sender_sort_code', 'sender_account_number', 'sender_roll_number',
            'amount', 'resolution', 'received_at',
        ])
        for credit in credits:
            cells = map(escape_csv_formula, [
                credit['prisoner_name'],
                credit['prisoner_number'],
                credit['prison'],
                credit['sender_name'],
                credit['sender_sort_code'],
                credit['sender_account_number'],
                credit['sender_roll_number'],
                '%.2f' % (Decimal(credit['amount']) / 100),
                credit['resolution'],
                credit['received_at'],
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
