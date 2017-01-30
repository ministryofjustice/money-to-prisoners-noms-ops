import datetime
import unittest
from unittest import mock

from security.forms import (
    SecurityForm, SendersForm, PrisonersForm, CreditsForm,
    ReviewCreditsForm
)


class SecurityFormTestCase(unittest.TestCase):
    def setUp(self):
        self.request = mock.MagicMock()
        self.mocked_connection = mock.patch('security.forms.get_connection')
        self.mocked_connection.start()
        self.mocked_prison_data = mock.patch('security.forms.get_prison_details_choices', return_value={
            'prisons': [('IXB', 'Prison 1'), ('INP', 'Prison 2')],
            'regions': [('London', 'London'), ('West Midlands', 'West Midlands')],
            'populations': [('male', 'Male'), ('female', 'Female'), ('adults', 'Adults')],
            'categories': [('A', 'Category A'), ('B', 'Category B')],
        })
        self.mocked_prison_data.start()

    def tearDown(self):
        self.mocked_connection.stop()
        self.mocked_prison_data.stop()

    def test_base_security_form(self):
        form = SecurityForm(self.request, data={})
        self.assertFalse(form.is_valid())

        form = SecurityForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, {
            'page': 1,
        })
        self.assertDictEqual(form.get_query_data(), {})
        self.assertEqual(form.query_string, '')

    def test_sender_list_form(self):
        # blank form
        expected_data = {
            'page': 1,
            'ordering': '-prisoner_count',
            'sender_name': '', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'prison': '', 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'prisoner_count__gte': None, 'credit_count__gte': None, 'credit_total__gte': None,
            'prisoner_count__lte': None, 'credit_count__lte': None, 'credit_total__lte': None,
            'card_number_last_digits': '', 'source': '',
        }
        form = SendersForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {'ordering': '-prisoner_count'})
        self.assertEqual(form.query_string, 'ordering=-prisoner_count')

        # valid forms
        expected_data = {
            'page': 1,
            'ordering': '-credit_total',
            'sender_name': 'Joh', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'prison': '', 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'prisoner_count__gte': None, 'credit_count__gte': None, 'credit_total__gte': None,
            'prisoner_count__lte': None, 'credit_count__lte': None, 'credit_total__lte': None,
            'card_number_last_digits': '', 'source': '',
        }
        form = SendersForm(self.request, data={'page': '1', 'ordering': '-credit_total', 'sender_name': 'Joh '})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {'ordering': '-credit_total', 'sender_name': 'Joh'})
        self.assertEqual(form.query_string, 'ordering=-credit_total&sender_name=Joh')

        # invalid forms
        form = SendersForm(self.request, data={})
        self.assertFalse(form.is_valid())
        form = SendersForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())
        form = SendersForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())
        form = SendersForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())

    def test_prisoner_list_form(self):
        # blank form
        expected_data = {
            'page': 1,
            'ordering': '-sender_count',
            'prisoner_number': '', 'prisoner_name': '',
            'prison': '', 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'sender_count__gte': None, 'credit_count__gte': None, 'credit_total__gte': None,
            'sender_count__lte': None, 'credit_count__lte': None, 'credit_total__lte': None,
        }
        form = PrisonersForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {'ordering': '-sender_count'})
        self.assertEqual(form.query_string, 'ordering=-sender_count')

        # valid forms
        expected_data = {
            'page': 1,
            'ordering': '-credit_total',
            'prisoner_number': '', 'prisoner_name': '',
            'prison': 'IXB', 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'sender_count__gte': None, 'credit_count__gte': None, 'credit_total__gte': None,
            'sender_count__lte': None, 'credit_count__lte': None, 'credit_total__lte': None,
        }
        form = PrisonersForm(self.request, data={'page': '1', 'ordering': '-credit_total', 'prison': 'IXB'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {'ordering': '-credit_total', 'prison': 'IXB'})
        self.assertEqual(form.query_string, 'ordering=-credit_total&prison=IXB')

        # invalid forms
        form = PrisonersForm(self.request, data={})
        self.assertFalse(form.is_valid())
        form = PrisonersForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())
        form = PrisonersForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())
        form = PrisonersForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())

    def test_credits_list_form(self):
        # blank form
        expected_data = {
            'page': 1,
            'ordering': '-received_at',
            'received_at__gte': None, 'received_at__lt': None,
            'prisoner_number': '', 'prisoner_name': '',
            'prison': '', 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'sender_name': '', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'amount_pattern': '', 'amount_exact': '', 'amount_pence': None, 'card_number_last_digits': '',
            'source': '',
        }
        form = CreditsForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {'ordering': '-received_at'})
        self.assertEqual(form.query_string, 'ordering=-received_at')

        # valid forms
        received_at__gte = datetime.date(2016, 5, 26)
        expected_data = {
            'page': 1,
            'ordering': '-amount',
            'received_at__gte': received_at__gte, 'received_at__lt': None,
            'prisoner_number': '', 'prisoner_name': '',
            'prison': '', 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'sender_name': '', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'amount_pattern': '', 'amount_exact': '', 'amount_pence': None, 'card_number_last_digits': '',
            'source': '',
        }
        form = CreditsForm(self.request, data={'page': '1', 'ordering': '-amount', 'received_at__gte': '26/5/2016'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {'ordering': '-amount', 'received_at__gte': received_at__gte})
        self.assertEqual(form.query_string, 'ordering=-amount&received_at__gte=2016-05-26')
        form = CreditsForm(self.request, data={'page': '1', 'amount_pattern': 'not_integral'})
        self.assertTrue(form.is_valid(), msg=form.errors.as_text())
        self.assertDictEqual(form.get_query_data(), {'ordering': '-received_at', 'exclude_amount__endswith': '00'})
        self.assertDictEqual(form.get_query_data(allow_parameter_manipulation=False),
                             {'ordering': '-received_at', 'amount_pattern': 'not_integral'})
        self.assertEqual(form.query_string, 'ordering=-received_at&amount_pattern=not_integral')

        # invalid forms
        form = CreditsForm(self.request, data={})
        self.assertFalse(form.is_valid())
        form = CreditsForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())
        form = CreditsForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())
        form = CreditsForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())


class ReviewCreditsFormTestCase(unittest.TestCase):

    @mock.patch('security.forms.get_connection')
    def test_review_credits_form(self, mock_get_connection):
        mock_get_connection().credits.get.return_value = {
            'count': 2,
            'results': [
                {
                    'id': 1,
                    'source': 'online',
                    'amount': 23000,
                    'intended_recipient': 'GEORGE MELLEY',
                    'prisoner_number': 'A1411AE', 'prisoner_name': 'GEORGE MELLEY',
                    'prison': 'LEI', 'prison_name': 'HMP LEEDS',
                    'sender_name': None, 'sender_email': 'HENRY MOORE',
                    'sender_sort_code': None, 'sender_account_number': None, 'sender_roll_number': None,
                    'resolution': 'pending',
                    'owner': None, 'owner_name': None,
                    'received_at': '2016-05-25T20:24:00Z', 'credited_at': None, 'refunded_at': None,
                },
                {
                    'id': 2,
                    'source': 'bank_transfer',
                    'amount': 27500,
                    'intended_recipient': None,
                    'prisoner_number': 'A1413AE', 'prisoner_name': 'NORMAN STANLEY FLETCHER',
                    'prison': 'LEI', 'prison_name': 'HMP LEEDS',
                    'sender_name': 'HEIDENREICH X',
                    'sender_sort_code': '219657', 'sender_account_number': '88447894', 'sender_roll_number': '',
                    'resolution': 'pending',
                    'owner': None, 'owner_name': None,
                    'received_at': '2016-05-22T23:00:00Z', 'credited_at': None, 'refunded_at': None,
                },
            ]
        }

        request = mock.MagicMock()
        form = ReviewCreditsForm(request, data={'comment_1': 'hold up'})
        self.assertEqual(len(form.credits), 2)
        self.assertTrue(form.is_valid())

        form.review()

        mock_get_connection().credits.comments.post.assert_called_once_with(
            [{'credit': 1, 'comment': 'hold up'}]
        )
        mock_get_connection().credits.actions.review.post.assert_called_once_with(
            {'credit_ids': [1, 2]}
        )
