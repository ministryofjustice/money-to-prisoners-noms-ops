import datetime
import json
import unittest
from unittest import mock

from django.http import QueryDict
from mtp_common.auth.test_utils import generate_tokens
import responses

from security.forms import (
    SecurityForm, SendersForm, PrisonersForm, CreditsForm,
    ReviewCreditsForm
)
from security.tests import api_url

mocked_prisons = {
    'count': 2,
    'results': [
        {
            'nomis_id': 'IXB', 'general_ledger_code': '10200042',
            'name': 'HMP Prison 1', 'short_name': 'Prison 1',
            'region': 'West Midlands',
            'categories': [{'description': 'Category A', 'name': 'A'}],
            'populations': [{'description': 'Adult', 'name': 'adult'}, {'description': 'Male', 'name': 'male'}],
        },
        {
            'nomis_id': 'INP', 'general_ledger_code': '10200015',
            'name': 'HMP & YOI Prison 2', 'short_name': 'Prison 2',
            'region': 'London',
            'categories': [{'description': 'Category B', 'name': 'B'}],
            'populations': [{'description': 'Adult', 'name': 'adult'}, {'description': 'Female', 'name': 'female'}],
        },
    ]
}


empty_response = {
    'count': 0,
    'results': [],
}


class SecurityFormTestCase(unittest.TestCase):

    def set_security_form_responses(self):
        responses.add(
            responses.GET,
            api_url('/prisons/'),
            json=mocked_prisons
        )
        responses.add(
            responses.GET,
            api_url('/senders/'),
            json=empty_response
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/'),
            json=empty_response
        )
        responses.add(
            responses.GET,
            api_url('/credits/'),
            json=empty_response
        )

    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens()
            )
        )
        self.disable_cache = mock.patch('security.models.cache')
        self.disable_cache.start().get.return_value = None

    def tearDown(self):
        self.disable_cache.stop()

    @responses.activate
    @mock.patch.object(SecurityForm, 'get_object_list_endpoint_path')
    def test_base_security_form(self, get_object_list_endpoint_path):
        # mock no results from API
        get_object_list_endpoint_path.return_value = '/test/'
        responses.add(
            responses.GET,
            api_url('/test/'),
            json=empty_response
        )

        expected_data = {'page': 1}
        form = SecurityForm(self.request, data={})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {})
        self.assertEqual(form.query_string, '')

        form = SecurityForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {})
        self.assertEqual(form.query_string, '')

    @responses.activate
    def test_sender_list_blank_form(self):
        self.set_security_form_responses()
        expected_data = {
            'page': 1,
            'ordering': '-prisoner_count',
            'sender_name': '', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'prisoner_count__gte': None, 'credit_count__gte': None, 'credit_total__gte': None,
            'prisoner_count__lte': None, 'credit_count__lte': None, 'credit_total__lte': None,
            'prison_count__gte': None, 'prison_count__lte': None,
            'card_number_last_digits': '', 'source': '', 'sender_email': '', 'sender_postcode': '',
        }
        form = SendersForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-prisoner_count'})
        self.assertEqual(form.query_string, 'ordering=-prisoner_count')

    @responses.activate
    def test_sender_list_valid_form(self):
        self.set_security_form_responses()
        expected_data = {
            'page': 1,
            'ordering': '-credit_total',
            'sender_name': 'Joh', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'prisoner_count__gte': None, 'credit_count__gte': None, 'credit_total__gte': None,
            'prisoner_count__lte': None, 'credit_count__lte': None, 'credit_total__lte': None,
            'prison_count__gte': None, 'prison_count__lte': None,
            'card_number_last_digits': '', 'source': '', 'sender_email': '', 'sender_postcode': '',
        }
        form = SendersForm(self.request, data={'page': '1', 'ordering': '-credit_total', 'sender_name': 'Joh '})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-credit_total', 'sender_name': 'Joh'})
        self.assertEqual(form.query_string, 'ordering=-credit_total&sender_name=Joh')

    @responses.activate
    def test_sender_list_invalid_forms(self):
        self.set_security_form_responses()
        form = SendersForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())
        form = SendersForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())
        form = SendersForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())

    @responses.activate
    def test_prisoner_list_blank_form(self):
        self.set_security_form_responses()
        expected_data = {
            'page': 1,
            'ordering': '-sender_count',
            'prisoner_number': '', 'prisoner_name': '',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'sender_count__gte': None, 'credit_count__gte': None, 'credit_total__gte': None,
            'sender_count__lte': None, 'credit_count__lte': None, 'credit_total__lte': None,
        }
        form = PrisonersForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-sender_count'})
        self.assertEqual(form.query_string, 'ordering=-sender_count')

    @responses.activate
    def test_prisoner_list_valid_form(self):
        self.set_security_form_responses()
        expected_data = {
            'page': 1,
            'ordering': '-credit_total',
            'prisoner_number': '', 'prisoner_name': 'John',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'sender_count__gte': None, 'credit_count__gte': None, 'credit_total__gte': None,
            'sender_count__lte': None, 'credit_count__lte': None, 'credit_total__lte': None,
        }
        form = PrisonersForm(self.request, data={'page': '1', 'ordering': '-credit_total', 'prisoner_name': ' John'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-credit_total', 'prisoner_name': 'John'})
        self.assertEqual(form.query_string, 'ordering=-credit_total&prisoner_name=John')

    @responses.activate
    def test_prisoner_list_invalid_forms(self):
        self.set_security_form_responses()
        form = PrisonersForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())
        form = PrisonersForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())
        form = PrisonersForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())

    @responses.activate
    def test_credits_list_blank_form(self):
        self.set_security_form_responses()
        expected_data = {
            'page': 1,
            'ordering': '-received_at',
            'received_at__gte': None, 'received_at__lt': None,
            'prisoner_number': '', 'prisoner_name': '',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'sender_name': '', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'amount_pattern': '', 'amount_exact': '', 'amount_pence': None, 'card_number_last_digits': '',
            'source': '', 'sender_email': '', 'sender_postcode': '', 'sender_ip_address': '',
        }
        form = CreditsForm(self.request, data={'page': '1'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-received_at'})
        self.assertEqual(form.query_string, 'ordering=-received_at')

    @responses.activate
    def test_credits_list_valid_forms(self):
        self.set_security_form_responses()
        received_at__gte = datetime.date(2016, 5, 26)
        expected_data = {
            'page': 1,
            'ordering': '-amount',
            'received_at__gte': received_at__gte, 'received_at__lt': None,
            'prisoner_number': '', 'prisoner_name': '',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'sender_name': '', 'sender_sort_code': '', 'sender_account_number': '', 'sender_roll_number': '',
            'amount_pattern': '', 'amount_exact': '', 'amount_pence': None, 'card_number_last_digits': '',
            'source': '', 'sender_email': '', 'sender_postcode': '', 'sender_ip_address': '',
        }
        form = CreditsForm(self.request, data={'page': '1', 'ordering': '-amount', 'received_at__gte': '26/5/2016'})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, expected_data)
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-amount', 'received_at__gte': received_at__gte})
        self.assertEqual(form.query_string, 'ordering=-amount&received_at__gte=2016-05-26')
        form = CreditsForm(self.request, data={'page': '1', 'amount_pattern': 'not_integral'})
        self.assertTrue(form.is_valid(), msg=form.errors.as_text())
        self.assertDictEqual(form.get_query_data(), {'ordering': '-received_at', 'exclude_amount__endswith': '00'})
        self.assertDictEqual(form.get_query_data(allow_parameter_manipulation=False),
                             {'ordering': '-received_at', 'amount_pattern': 'not_integral'})
        self.assertEqual(form.query_string, 'ordering=-received_at&amount_pattern=not_integral')

    @responses.activate
    def test_credits_list_invalid_forms(self):
        self.set_security_form_responses()
        form = CreditsForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())
        form = CreditsForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())
        form = CreditsForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())

    @responses.activate
    def test_filtering_by_one_prison(self):
        self.set_security_form_responses()
        for form_class in (SendersForm, PrisonersForm, CreditsForm):
            form = form_class(self.request, data=QueryDict('prison=INP', mutable=True))
            initial_ordering = form['ordering'].initial
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.get_query_data(), {'ordering': initial_ordering, 'prison': ['INP']})
            self.assertEqual(form.query_string, 'ordering=%s&prison=INP' % initial_ordering)

    @responses.activate
    def test_filtering_by_many_prisons(self):
        self.set_security_form_responses()
        for form_class in (SendersForm, PrisonersForm, CreditsForm):
            form = form_class(self.request, data=QueryDict('prison=IXB&prison=INP', mutable=True))
            initial_ordering = form['ordering'].initial
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.get_query_data(), {'ordering': initial_ordering, 'prison': ['INP', 'IXB']})
            self.assertEqual(form.query_string, 'ordering=%s&prison=INP&prison=IXB' % initial_ordering)

    @responses.activate
    def test_filtering_by_many_prisons_alternate(self):
        self.set_security_form_responses()
        for form_class in (SendersForm, PrisonersForm, CreditsForm):
            form = form_class(self.request, data=QueryDict('prison=IXB,INP,', mutable=True))
            initial_ordering = form['ordering'].initial
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.get_query_data(), {'ordering': initial_ordering, 'prison': ['INP', 'IXB']})
            self.assertEqual(form.query_string, 'ordering=%s&prison=INP&prison=IXB' % initial_ordering)


class ReviewCreditsFormTestCase(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens()
            )
        )

    @responses.activate
    def test_review_credits_form(self):
        responses.add(
            responses.GET,
            api_url('/credits/'),
            json={
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
        )
        responses.add(
            responses.POST,
            api_url('/credits/comments/'),
        )
        responses.add(
            responses.POST,
            api_url('/credits/actions/review/'),
        )

        form = ReviewCreditsForm(self.request, data={'comment_1': 'hold up'})
        self.assertEqual(len(form.credits), 2)
        self.assertTrue(form.is_valid())

        form.review()

        self.assertEqual(
            json.loads(responses.calls[-2].request.body.decode()),
            [{'credit': 1, 'comment': 'hold up'}]
        )
        self.assertEqual(
            json.loads(responses.calls[-1].request.body.decode()),
            {'credit_ids': [1, 2]}
        )
