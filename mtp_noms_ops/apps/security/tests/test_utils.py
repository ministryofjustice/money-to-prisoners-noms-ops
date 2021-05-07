import datetime
import unittest

from unittest import mock

from django.utils.timezone import localtime, make_aware, utc
from mtp_common.test_utils import silence_logger

from security.templatetags.security import genitive, currency, pence, format_sort_code, check_description
from security.utils import (
    convert_date_fields,
    NameSet,
    EmailSet,
    remove_whitespaces_and_hyphens,
    get_need_attention_date,
)


class UtilTestCase(unittest.TestCase):
    def test_genitive_filter(self):
        self.assertEqual(genitive(None), None)
        self.assertEqual(genitive(123), 123)
        self.assertEqual(genitive(''), '')
        self.assertEqual(genitive('Joe'), 'Joe’s')
        self.assertEqual(genitive('James'), 'James’')

    def test_currency_formatting(self):
        self.assertEqual(currency(None), None)
        self.assertEqual(currency(''), '')
        self.assertEqual(currency('a'), 'a')
        self.assertEqual(currency(0), '£0.00')
        self.assertEqual(currency(1), '£0.01')
        self.assertEqual(currency(13500), '£135.00')
        self.assertEqual(currency(123500), '£1,235.00')

    def test_pence_formatting(self):
        self.assertEqual(pence(None), None)
        self.assertEqual(pence(''), '')
        self.assertEqual(pence('a'), 'a')
        self.assertEqual(pence(0), '0p')
        self.assertEqual(pence(1), '1p')
        self.assertEqual(pence(99), '99p')
        self.assertEqual(pence(100), '£1.00')

    def test_sort_code_formatting(self):
        self.assertEqual(format_sort_code(None), '—')
        self.assertEqual(format_sort_code(''), '—')
        self.assertEqual(format_sort_code('123456'), '12-34-56')
        self.assertEqual(format_sort_code('1234567'), '1234567')

    def test_name_set(self):
        names = NameSet(['A', 'a', 'A ', ' Aa ', 'John A.', 'MR. JOHN A.'])
        self.assertSequenceEqual(names, ('A', ' Aa ', 'John A.', 'MR. JOHN A.'))
        names.add('JOHN')
        names.add('Mr John')
        self.assertSequenceEqual(names, ('A', ' Aa ', 'John A.', 'MR. JOHN A.', 'JOHN', 'Mr John'))

        names = NameSet(['A', 'a', 'A ', ' Aa ', 'John A.', 'MR. JOHN A.'], strip_titles=True)
        self.assertSequenceEqual(names, ('A', ' Aa ', 'John A.'))
        names.add('JOHN')
        names.add('Mr John')
        self.assertSequenceEqual(names, ('A', ' Aa ', 'John A.', 'JOHN'))

    def test_email_set(self):
        emails = EmailSet(['abc@example.com', 'ABC@EXAMPLE.COM', 'abc@example.co.uk',
                           'abc@example.com ', 'Abc@example.com', ''])
        self.assertSequenceEqual(emails, ('abc@example.com', 'abc@example.co.uk', ''))

    def test_check_description(self):
        def run_filter(d):
            check = {'description': d}
            return check_description(check)

        cases = [
            # original form
            (
                'Credit matched: Compliaces rules failed',
                'Compliaces rules failed.',
            ),
            (
                'Credit matched: Credit matched rule 1. Credit matched rule 5',
                'Credit matched rule 1. Credit matched rule 5.',
            ),
            # original form with stripped prefix
            (
                'Compliaces rules failed',
                'Compliaces rules failed.',
            ),
            (
                'Credit matched rule 1. Credit matched rule 5',
                'Credit matched rule 1. Credit matched rule 5.',
            ),
            # new form
            (
                ['Compliaces rules failed'],
                'Compliaces rules failed.',
            ),
            (
                ['Credit matched rule 1', 'Credit matched rule 5'],
                'Credit matched rule 1. Credit matched rule 5.',
            ),
        ]
        for description, expected in cases:
            # label prefix always expected
            self.assertIn('Rules:', run_filter(description))
            # historic prefix should be stripped off
            self.assertNotIn('Credit matched:', run_filter(description))
            self.assertIn(expected, run_filter(description))


class RemoveWhitespacesAndHyphensTestCase(unittest.TestCase):
    """
    Tests related to remove_whitespaces_and_hyphens.
    """

    def test_falsy_value_returns_value(self):
        """
        Test that if `value` is falsy, the function returns `value` untouched.
        """
        for value in (None, ''):
            self.assertEqual(
                remove_whitespaces_and_hyphens(value),
                value,
            )

    def test_replaces_whitespaces_and_hyphens(self):
        """
        Test that the function gets rid of whitespaces and hyphens.
        """
        self.assertEqual(
            remove_whitespaces_and_hyphens(' SW 1A-1a A '),
            'SW1A1aA',
        )


class GetNeedAttentionDateTestCase(unittest.TestCase):
    """
    Test that the get needs attention date set up returns the date
    that would be 3 days ago, inclusively
    """
    @mock.patch('security.utils.timezone', mock.MagicMock(
        now=mock.MagicMock(return_value=make_aware(datetime.datetime(2019, 7, 3, 9)))
    ))
    def test_returns_date_3_days_ago_inclusively(self):
        self.assertEqual(get_need_attention_date(), make_aware(datetime.datetime(2019, 7, 1)))


class ConvertDateFieldsTestCase(unittest.TestCase):
    """
    Tests related to the convert_date_fields function.
    """

    def test_converts_lists(self):
        """
        Test that the function converts dates and datetimes correctly when the input arg is a list.
        """
        objs = [
            {
                'started_at': '2019-07-01',
                'received_at': '2019-07-02T10:00:00Z',  # utc
                'credited_at': '2019-07-03',
                'refunded_at': '2019-07-04T11:01:00+01:00',  # BST+1
                'created': '2019-07-05',
                'triggered_at': '2019-07-06T10:02:00Z',
            }
        ]
        converted_objects = convert_date_fields(objs)
        self.assertEqual(
            converted_objects[0],
            {
                'started_at': datetime.date(2019, 7, 1),
                'received_at': localtime(datetime.datetime(2019, 7, 2, 10, 0, tzinfo=utc)),
                'credited_at': datetime.date(2019, 7, 3),
                'refunded_at': make_aware(datetime.datetime(2019, 7, 4, 11, 1)),
                'created': datetime.date(2019, 7, 5),
                'triggered_at': localtime(datetime.datetime(2019, 7, 6, 10, 2, tzinfo=utc)),
            },
        )

    def test_converts_objects(self):
        """
        Test that the function converts dates and datetimes correctly when the input arg is an object.
        """
        obj = {
            'started_at': '2019-07-01',
            'received_at': '2019-07-02T10:00:00Z',  # utc
            'credited_at': '2019-07-03',
            'refunded_at': '2019-07-04T11:01:00+01:00',  # BST+1
            'created': '2019-07-05',
            'triggered_at': '2019-07-06T10:02:00Z',
        }
        self.assertEqual(
            convert_date_fields(obj),
            {
                'started_at': datetime.date(2019, 7, 1),
                'received_at': localtime(datetime.datetime(2019, 7, 2, 10, 0, tzinfo=utc)),
                'credited_at': datetime.date(2019, 7, 3),
                'refunded_at': make_aware(datetime.datetime(2019, 7, 4, 11, 1)),
                'created': datetime.date(2019, 7, 5),
                'triggered_at': localtime(datetime.datetime(2019, 7, 6, 10, 2, tzinfo=utc)),
            },
        )

    def test_include_nested(self):
        """
        Test that if include_nested = True, nested values are converted as well.
        """
        objs = [
            {
                'field': {
                    'started_at': '2019-07-01',
                    'received_at': '2019-07-02T10:00:00Z',  # utc
                },
            }
        ]
        converted_objects = convert_date_fields(objs, include_nested=True)
        self.assertEqual(
            converted_objects[0],
            {
                'field': {
                    'started_at': datetime.date(2019, 7, 1),
                    'received_at': localtime(datetime.datetime(2019, 7, 2, 10, 0, tzinfo=utc)),
                },
            },
        )

    def test_handles_timezone_aware_and_naive_datetimes(self):
        objs = [{
            # dates in BST
            'started_at': '2021-05-07',
            'received_at': '2021-05-07T12:00:00',  # naive so assumed Europe/London (i.e. BST)
            'credited_at': '2021-05-07T12:00:00Z',  # 12pm UTC is 1pm in Europe/London (i.e. BST)
            'refunded_at': '2021-05-07T12:00:00+01:00',  # explicit time zone
            # dates in GMT
            'created': '2021-03-01T00:00:00',  # naive so assumed Europe/London (i.e. GMT)
            'triggered_at': '2021-03-01T00:00:00Z',  # 12am UTC is 12am in Europe/London (i.e. GMT)
            'actioned_at': '2021-03-01T00:00:00+00:00',  # explicit time zone
        }]
        converted_objects = convert_date_fields(objs)
        self.assertEqual(
            converted_objects[0],
            {
                'started_at': datetime.date(2021, 5, 7),
                'received_at': make_aware(datetime.datetime(2021, 5, 7, 12)),
                'credited_at': make_aware(datetime.datetime(2021, 5, 7, 13)),
                'refunded_at': make_aware(datetime.datetime(2021, 5, 7, 12)),
                'created': make_aware(datetime.datetime(2021, 3, 1)),
                'triggered_at': make_aware(datetime.datetime(2021, 3, 1)),
                'actioned_at': make_aware(datetime.datetime(2021, 3, 1)),
            },
        )

    def test_doesnt_convert_non_strings(self):
        """
        Test that if the values are not strings, they are not converted.
        """
        objs = [
            {
                'started_at': 1,
                'received_at': ['date'],
                'credited_at': {'key': 'value'},
                'refunded_at': datetime.date(2019, 7, 1),
            }
        ]
        converted_objects = convert_date_fields(objs)
        self.assertEqual(
            converted_objects[0],
            {
                'started_at': 1,
                'received_at': ['date'],
                'credited_at': {'key': 'value'},
                'refunded_at': datetime.date(2019, 7, 1),
            }
        )

    def test_doesnt_convert_falsy_values(self):
        """
        Test that if the values are falsy, they are not converted.
        """
        objs = [
            {
                'started_at': None,
                'received_at': '',
            }
        ]
        converted_objects = convert_date_fields(objs)
        self.assertEqual(
            converted_objects[0],
            {
                'started_at': None,
                'received_at': '',
            }
        )

    def test_handles_invalid_strings(self):
        """
        Test that if the values are invalid, they are not converted.
        """
        objs = [
            {
                'started_at': '2019-13-01',
                'received_at': 'invalid',
            }
        ]
        with silence_logger():
            converted_objects = convert_date_fields(objs)
        self.assertEqual(
            converted_objects[0],
            {
                'started_at': '2019-13-01',
                'received_at': 'invalid',
            }
        )
