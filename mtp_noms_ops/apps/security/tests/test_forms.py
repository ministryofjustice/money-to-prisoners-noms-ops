import datetime
from collections import namedtuple
import json
import unittest
from unittest import mock

from django.http import QueryDict
from django.test import SimpleTestCase
from mtp_common.auth.test_utils import generate_tokens
import responses

from security.forms.object_base import SecurityForm
from security.forms.object_list import (
    SendersForm,
    SendersFormV2,
    PrisonersForm,
    CreditsForm,
    DisbursementsForm,
)
from security.forms.review import ReviewCreditsForm
from security.tests import api_url


def mock_prison_response(rsps):
    prisons = [
        {
            'nomis_id': 'IXB', 'general_ledger_code': '10200042',
            'name': 'HMP Prison 1', 'short_name': 'Prison 1',
            'region': 'West Midlands',
            'categories': [{'description': 'Category A', 'name': 'A'}],
            'populations': [
                {'description': 'Adult', 'name': 'adult'},
                {'description': 'Male', 'name': 'male'}
            ],
        },
        {
            'nomis_id': 'INP', 'general_ledger_code': '10200015',
            'name': 'HMP & YOI Prison 2', 'short_name': 'Prison 2',
            'region': 'London',
            'categories': [{'description': 'Category B', 'name': 'B'}],
            'populations': [
                {'description': 'Adult', 'name': 'adult'},
                {'description': 'Female', 'name': 'female'}
            ],
        },
    ]
    rsps.add(
        rsps.GET,
        api_url('/prisons/'),
        json={
            'count': 2,
            'results': prisons,
        }
    )

    return prisons


def mock_empty_response(rsps, path):
    rsps.add(
        rsps.GET,
        api_url(path),
        json={
            'count': 0,
            'results': [],
        }
    )


class SecurityFormTestCase(SimpleTestCase):
    form_class = None

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

    @mock.patch.object(SecurityForm, 'get_object_list_endpoint_path')
    def test_base_security_form(self, get_object_list_endpoint_path):
        if self.form_class:
            return

        # mock no results from API
        get_object_list_endpoint_path.return_value = '/test/'
        expected_data = {'page': 1}

        with responses.RequestsMock() as rsps:
            mock_empty_response(rsps, '/test/')
            form = SecurityForm(self.request, data={})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
            self.assertDictEqual(form.get_query_data(), {})
            self.assertEqual(form.query_string, '')

        with responses.RequestsMock() as rsps:
            mock_empty_response(rsps, '/test/')
            form = SecurityForm(self.request, data={'page': '1'})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
            self.assertDictEqual(form.get_query_data(), {})
            self.assertEqual(form.query_string, '')

    def test_filtering_by_one_prison(self):
        if not self.form_class:
            return
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data=QueryDict('prison=INP', mutable=True))
        initial_ordering = form['ordering'].initial
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.get_query_data(), {'ordering': initial_ordering, 'prison': ['INP']})
        self.assertEqual(form.query_string, 'ordering=%s&prison=INP' % initial_ordering)

    def test_filtering_by_many_prisons(self):
        if not self.form_class:
            return
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data=QueryDict('prison=IXB&prison=INP', mutable=True))
        initial_ordering = form['ordering'].initial
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.get_query_data(), {'ordering': initial_ordering, 'prison': ['INP', 'IXB']})
        self.assertEqual(form.query_string, 'ordering=%s&prison=INP&prison=IXB' % initial_ordering)

    def test_filtering_by_many_prisons_alternate(self):
        if not self.form_class:
            return
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data=QueryDict('prison=IXB,INP,', mutable=True))
        initial_ordering = form['ordering'].initial
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.get_query_data(), {'ordering': initial_ordering, 'prison': ['INP', 'IXB']})
        self.assertEqual(form.query_string, 'ordering=%s&prison=INP&prison=IXB' % initial_ordering)


class SenderFormTestCase(SecurityFormTestCase):
    """
    TODO: delete after search V2 goes live.
    """
    form_class = SendersForm
    api_list_path = '/senders/'

    def test_sender_list_blank_form(self):
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
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)
            form = SendersForm(self.request, data={'page': '1'})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-prisoner_count'})
        self.assertEqual(form.query_string, 'ordering=-prisoner_count')

    def test_sender_list_valid_form(self):
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
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)
            form = SendersForm(self.request, data={'page': '1', 'ordering': '-credit_total', 'sender_name': 'Joh '})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-credit_total', 'sender_name': 'Joh'})
        self.assertEqual(form.query_string, 'ordering=-credit_total&sender_name=Joh')

    def test_sender_list_invalid_forms(self):
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = SendersForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = SendersForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = SendersForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())


class SenderFormV2TestCase(SecurityFormTestCase):
    """
    Tests related to the SenderFormV2.
    """

    form_class = SendersFormV2
    api_list_path = '/senders/'

    @responses.activate
    def test_blank_form(self):
        """
        Test that if no data is passed in, the default values are used instead.
        """
        mock_prison_response(responses)
        mock_empty_response(responses, self.api_list_path)

        form = SendersFormV2(self.request, data={})

        self.assertTrue(form.is_valid())
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 1,
                'ordering': '-prisoner_count',
                'prison': [],
                'search': '',
            },
        )
        self.assertDictEqual(
            form.get_query_data(),
            {'ordering': '-prisoner_count'},
        )
        self.assertEqual(
            form.query_string,
            'ordering=-prisoner_count',
        )
        self.assertEqual(len(responses.calls), 2)
        self.assertEqual(
            responses.calls[-1].request.path_url,
            f'{self.api_list_path}?offset=0&limit=20&ordering=-prisoner_count',
        )

    @responses.activate
    def test_valid(self):
        """
        Test that if data is passed in, the API query string is constructed as expected.
        """
        prisons = mock_prison_response(responses)
        mock_empty_response(responses, self.api_list_path)

        form = SendersFormV2(
            self.request,
            data={
                'page': 2,
                'ordering': '-credit_total',
                'prison': [
                    prisons[0]['nomis_id'],
                ],
                'search': 'Joh',
            },
        )

        self.assertTrue(form.is_valid())
        self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 2,
                'ordering': '-credit_total',
                'prison': [
                    prisons[0]['nomis_id'],
                ],
                'search': 'Joh',
            },
        )

        self.assertDictEqual(
            form.get_query_data(),
            {
                'ordering': '-credit_total',
                'prison': [
                    prisons[0]['nomis_id'],
                ],
                'search': 'Joh',
            },
        )
        self.assertEqual(len(responses.calls), 2)
        self.assertEqual(
            form.query_string,
            'ordering=-credit_total&prison=IXB&search=Joh',
        )
        self.assertEqual(
            responses.calls[-1].request.path_url,
            f'{self.api_list_path}?offset=20&limit=20&ordering=-credit_total&prison=IXB&search=Joh',
        )

    def test_invalid(self):
        """
        Test validation errors.
        """
        ValidationScenario = namedtuple('ValidationScenario', 'data errors')

        scenarios = [
            ValidationScenario(
                {'page': '0'},
                {'page': ['Ensure this value is greater than or equal to 1.']},
            ),
            ValidationScenario(
                {'ordering': 'prison'},
                {'ordering': ['Select a valid choice. prison is not one of the available choices.']},
            ),
            ValidationScenario(
                {'prison': ['invalid']},
                {'prison': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
        ]

        for scenario in scenarios:
            with responses.RequestsMock() as rsps:
                mock_prison_response(rsps)
                form = SendersFormV2(self.request, data=scenario.data)
            self.assertFalse(form.is_valid())
            self.assertDictEqual(form.errors, scenario.errors)


class PrisonerFormTestCase(SecurityFormTestCase):
    form_class = PrisonersForm
    api_list_path = '/prisoners/'

    def test_prisoner_list_blank_form(self):
        expected_data = {
            'page': 1,
            'ordering': '-sender_count',
            'prisoner_number': '', 'prisoner_name': '',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'credit_count__gte': None, 'credit_count__lte': None,
            'credit_total__gte': None, 'credit_total__lte': None,
            'sender_count__gte': None, 'sender_count__lte': None,
            'disbursement_count__gte': None, 'disbursement_count__lte': None,
            'disbursement_total__gte': None, 'disbursement_total__lte': None,
            'recipient_count__gte': None, 'recipient_count__lte': None,
        }
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)
            form = PrisonersForm(self.request, data={'page': '1'})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-sender_count'})
        self.assertEqual(form.query_string, 'ordering=-sender_count')

    def test_prisoner_list_valid_form(self):
        expected_data = {
            'page': 1,
            'ordering': '-credit_total',
            'prisoner_number': '', 'prisoner_name': 'John',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'credit_count__gte': None, 'credit_count__lte': None,
            'credit_total__gte': None, 'credit_total__lte': None,
            'sender_count__gte': None, 'sender_count__lte': None,
            'disbursement_count__gte': None, 'disbursement_count__lte': None,
            'disbursement_total__gte': None, 'disbursement_total__lte': None,
            'recipient_count__gte': None, 'recipient_count__lte': None,
        }
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)
            form = PrisonersForm(
                self.request,
                data={'page': '1', 'ordering': '-credit_total', 'prisoner_name': ' John'},
            )
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-credit_total', 'prisoner_name': 'John'})
        self.assertEqual(form.query_string, 'ordering=-credit_total&prisoner_name=John')

    def test_prisoner_list_invalid_forms(self):
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = PrisonersForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = PrisonersForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = PrisonersForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())


class CreditFormTestCase(SecurityFormTestCase):
    form_class = CreditsForm
    api_list_path = '/credits/'

    def test_credits_list_blank_form(self):
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
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)
            form = CreditsForm(self.request, data={'page': '1'})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-received_at'})
        self.assertEqual(form.query_string, 'ordering=-received_at')

    def test_credits_list_valid_forms(self):
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
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)
            form = CreditsForm(self.request, data={'page': '1', 'ordering': '-amount', 'received_at__gte': '26/5/2016'})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-amount', 'received_at__gte': received_at__gte})
        self.assertEqual(form.query_string, 'ordering=-amount&received_at__gte=2016-05-26')

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = CreditsForm(self.request, data={'page': '1', 'amount_pattern': 'not_integral'})
        self.assertTrue(form.is_valid(), msg=form.errors.as_text())
        self.assertDictEqual(form.get_query_data(), {'ordering': '-received_at', 'exclude_amount__endswith': '00'})
        self.assertDictEqual(form.get_query_data(allow_parameter_manipulation=False),
                             {'ordering': '-received_at', 'amount_pattern': 'not_integral'})
        self.assertEqual(form.query_string, 'ordering=-received_at&amount_pattern=not_integral')

    def test_credits_list_invalid_forms(self):
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = CreditsForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = CreditsForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = CreditsForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())


class DisbursementFormTestCase(SecurityFormTestCase):
    form_class = DisbursementsForm
    api_list_path = '/disbursements/'

    def test_disbursements_list_blank_form(self):
        expected_data = {
            'page': 1,
            'ordering': '-created',
            'created__gte': None, 'created__lt': None,
            'amount_pattern': '', 'amount_exact': '', 'amount_pence': None,
            'prisoner_number': '', 'prisoner_name': '',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'method': '', 'recipient_name': '', 'recipient_email': '', 'city': '', 'postcode': '',
            'sort_code': '', 'account_number': '', 'roll_number': '',
            'invoice_number': '',
        }
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)
            form = DisbursementsForm(self.request, data={'page': '1'})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-created'})
        self.assertEqual(form.query_string, 'ordering=-created')

    def test_disbursements_list_valid_forms(self):
        created__gte = datetime.date(2016, 5, 26)
        expected_data = {
            'page': 1,
            'ordering': '-amount',
            'created__gte': created__gte, 'created__lt': None,
            'amount_pattern': '', 'amount_exact': '', 'amount_pence': None,
            'prisoner_number': '', 'prisoner_name': '',
            'prison': [], 'prison_region': '', 'prison_population': '', 'prison_category': '',
            'method': '', 'recipient_name': '', 'recipient_email': '', 'city': '', 'postcode': '',
            'sort_code': '', 'account_number': '', 'roll_number': '',
            'invoice_number': '',
        }
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)
            form = DisbursementsForm(
                self.request,
                data={'page': '1', 'ordering': '-amount', 'created__gte': '26/5/2016'},
            )
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-amount', 'created__gte': created__gte})
        self.assertEqual(form.query_string, 'ordering=-amount&created__gte=2016-05-26')

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = DisbursementsForm(self.request, data={'page': '1', 'amount_pattern': 'not_integral'})
        self.assertTrue(form.is_valid(), msg=form.errors.as_text())
        self.assertDictEqual(form.get_query_data(), {'ordering': '-created', 'exclude_amount__endswith': '00'})
        self.assertDictEqual(form.get_query_data(allow_parameter_manipulation=False),
                             {'ordering': '-created', 'amount_pattern': 'not_integral'})
        self.assertEqual(form.query_string, 'ordering=-created&amount_pattern=not_integral')

    def test_disbursements_list_invalid_forms(self):
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = DisbursementsForm(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = DisbursementsForm(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = DisbursementsForm(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())


class ReviewCreditsFormTestCase(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens()
            )
        )

    def test_review_credits_form(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
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
            rsps.add(
                rsps.POST,
                api_url('/credits/comments/'),
            )

            form = ReviewCreditsForm(self.request, data={'comment_1': 'hold up'})
            self.assertTrue(form.is_valid())
            self.assertEqual(len(form.credits), 2)

            rsps.add(
                rsps.POST,
                api_url('/credits/actions/review/'),
            )
            form.review()
            self.assertEqual(
                json.loads(rsps.calls[-2].request.body.decode()),
                [{'credit': 1, 'comment': 'hold up'}]
            )
            self.assertEqual(
                json.loads(rsps.calls[-1].request.body.decode()),
                {'credit_ids': [1, 2]}
            )
