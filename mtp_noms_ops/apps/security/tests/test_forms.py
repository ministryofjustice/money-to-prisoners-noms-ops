import datetime
import unittest
from unittest import mock

from security.forms import SecurityForm, SenderGroupedForm, PrisonerGroupedForm, CreditsForm


class SecurityFormTestCase(unittest.TestCase):
    def setUp(self):
        self.request = mock.MagicMock()
        self.mocked_connection = mock.patch('security.forms.get_connection')
        self.mocked_connection.start()
        self.mocked_prison_data = mock.patch('security.forms.get_prisons_and_regions', return_value={
            'prisons': [('IXB', 'Prison 1'), ('INP', 'Prison 2')],
            'regions': [('London', 'London'), ('West Midlands', 'West Midlands')],
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
            'received_at_0': None,
            'received_at_1': None,
        })
        self.assertDictEqual(form.get_query_data(), {})
        self.assertEqual(form.query_string, '')
        self.assertSequenceEqual(form.page_range, [])

    def test_sender_list_form(self):
        # blank form
        expected_data = {
            'page': 1,
            'ordering': '',
            'sender_name': '', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'prison': '', 'prison_region': '', 'prison_gender': '',
            'received_at_0': None, 'prisoner_count_0': None, 'credit_count_0': None, 'credit_total_0': None,
            'received_at_1': None, 'prisoner_count_1': None, 'credit_count_1': None, 'credit_total_1': None,
        }
        form = SenderGroupedForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {})
        self.assertEqual(form.query_string, '')

        # valid forms
        expected_data = {
            'page': 1,
            'ordering': '-credit_total',
            'sender_name': 'Joh', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'prison': '', 'prison_region': '', 'prison_gender': '',
            'received_at_0': None, 'prisoner_count_0': None, 'credit_count_0': None, 'credit_total_0': None,
            'received_at_1': None, 'prisoner_count_1': None, 'credit_count_1': None, 'credit_total_1': None,
        }
        form = SenderGroupedForm(self.request, data={'page': '1', 'ordering': '-credit_total', 'sender_name': 'Joh '})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {'ordering': '-credit_total', 'sender_name': 'Joh'})
        self.assertEqual(form.query_string, 'ordering=-credit_total&sender_name=Joh')

        # invalid forms
        form = SenderGroupedForm(self.request, data={})
        self.assertFalse(form.is_valid())
        form = SenderGroupedForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())
        form = SenderGroupedForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())
        form = SenderGroupedForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())

    def test_prisoner_list_form(self):
        # blank form
        expected_data = {
            'page': 1,
            'ordering': '',
            'prisoner_number': '', 'prisoner_name': '',
            'prison': '', 'prison_region': '', 'prison_gender': '',
            'received_at_0': None, 'sender_count_0': None, 'credit_count_0': None, 'credit_total_0': None,
            'received_at_1': None, 'sender_count_1': None, 'credit_count_1': None, 'credit_total_1': None,
        }
        form = PrisonerGroupedForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {})
        self.assertEqual(form.query_string, '')

        # valid forms
        expected_data = {
            'page': 1,
            'ordering': '-credit_total',
            'prisoner_number': '', 'prisoner_name': '',
            'prison': 'IXB', 'prison_region': '', 'prison_gender': '',
            'received_at_0': None, 'sender_count_0': None, 'credit_count_0': None, 'credit_total_0': None,
            'received_at_1': None, 'sender_count_1': None, 'credit_count_1': None, 'credit_total_1': None,
        }
        form = PrisonerGroupedForm(self.request, data={'page': '1', 'ordering': '-credit_total', 'prison': 'IXB'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {'ordering': '-credit_total', 'prison': 'IXB'})
        self.assertEqual(form.query_string, 'ordering=-credit_total&prison=IXB')

        # invalid forms
        form = PrisonerGroupedForm(self.request, data={})
        self.assertFalse(form.is_valid())
        form = PrisonerGroupedForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())
        form = PrisonerGroupedForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())
        form = PrisonerGroupedForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())

    def test_credits_list_form(self):
        # blank form
        expected_data = {
            'page': 1,
            'ordering': '',
            'received_at_0': None, 'received_at_1': None,
            'prisoner_number': '', 'prisoner_name': '',
            'prison': '', 'prison_region': '', 'prison_gender': '',
            'sender_name': '', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'amount': '', 'amount_pattern': '', 'amount_pence': None,
        }
        form = CreditsForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {})
        self.assertEqual(form.query_string, '')

        # valid forms
        received_at_0 = datetime.date(2016, 5, 26)
        expected_data = {
            'page': 1,
            'ordering': '-amount',
            'received_at_0': received_at_0, 'received_at_1': None,
            'prisoner_number': '', 'prisoner_name': '',
            'prison': '', 'prison_region': '', 'prison_gender': '',
            'sender_name': '', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'amount': '', 'amount_pattern': '', 'amount_pence': None,
        }
        form = CreditsForm(self.request, data={'page': '1', 'ordering': '-amount', 'received_at_0': '26/5/2016'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertDictEqual(form.get_query_data(), {'ordering': '-amount', 'received_at_0': received_at_0})
        self.assertEqual(form.query_string, 'received_at_0=2016-05-26&ordering=-amount')

        # invalid forms
        form = CreditsForm(self.request, data={})
        self.assertFalse(form.is_valid())
        form = CreditsForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())
        form = CreditsForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())
        form = CreditsForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())
