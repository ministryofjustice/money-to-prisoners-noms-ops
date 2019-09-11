import datetime
from collections import namedtuple
import json
import unittest
from unittest import mock
from urllib.parse import parse_qs

from django.http import QueryDict
from django.test import SimpleTestCase
from mtp_common.auth.test_utils import generate_tokens
import responses

from security.forms.object_base import AmountPattern, SecurityForm
from security.forms.object_list import (
    AmountSearchFormMixin,
    CreditsForm,
    CreditsFormV2,
    DisbursementsForm,
    DisbursementsFormV2,
    PaymentMethodSearchFormMixin,
    PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
    PrisonersForm,
    PrisonersFormV2,
    PrisonSelectorSearchFormMixin,
    SendersForm,
    SendersFormV2,
)
from security.forms.review import ReviewCreditsForm
from security.models import PaymentMethod
from security.tests import api_url


ValidationScenario = namedtuple('ValidationScenario', 'data expected_errors')

SAMPLE_PRISONS = [
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


def mock_prison_response(rsps):
    rsps.add(
        rsps.GET,
        api_url('/prisons/'),
        json={
            'count': len(SAMPLE_PRISONS),
            'results': SAMPLE_PRISONS,
        }
    )


def mock_empty_response(rsps, path):
    rsps.add(
        rsps.GET,
        api_url(path),
        json={
            'count': 0,
            'results': [],
        }
    )


class MyAmountSearchForm(AmountSearchFormMixin, SecurityForm):
    """
    SecurityForm used to test AmountSearchFormMixin.
    """


class MyPrisonSelectorSearchForm(PrisonSelectorSearchFormMixin, SecurityForm):
    """
    SecurityForm used to test PrisonSelectorSearchFormMixin.
    """


class MyPaymentMethodSearchForm(PaymentMethodSearchFormMixin, SecurityForm):
    """
    SecurityForm used to test PaymentMethodSearchFormMixin.
    """

    def get_payment_method_choices(self):
        return (
            (PaymentMethod.bank_transfer.name, PaymentMethod.bank_transfer.value),
            (PaymentMethod.online.name, PaymentMethod.online.value),
            (PaymentMethod.cheque.name, PaymentMethod.cheque.value),
        )


class AmountSearchFormMixinTestCase(SimpleTestCase):
    """
    Tests for the AmountSearchFormMixin.
    """

    def test_valid(self):
        """
        Test valid scenarios.

        Note: amount_exact is reset when amount_pattern is not `exact` and
        amount_pence is reset when amount_pattern is not `pence`.
        """
        scenarios = [
            # amount_pattern == 'exact' and amount_exact value
            (
                {
                    'amount_pattern': AmountPattern.exact.name,
                    'amount_exact': '£100',
                },
                {
                    'page': 1,
                    'amount_pattern': AmountPattern.exact.name,
                    'amount_exact': '£100',
                    'amount_pence': '',
                },
                {
                    'amount': '10000',
                },
            ),

            # amount_pattern == 'pence' and amount_pence value
            (
                {
                    'amount_pattern': AmountPattern.pence.name,
                    'amount_pence': 99,
                },
                {
                    'page': 1,
                    'amount_pattern': AmountPattern.pence.name,
                    'amount_pence': 99,
                    'amount_exact': '',
                },
                {
                    'amount__endswith': '99',
                },
            ),

            # amount_pattern == 'pence' and amount_pence == 0
            (
                {
                    'amount_pattern': AmountPattern.pence.name,
                    'amount_pence': 0,
                },
                {
                    'page': 1,
                    'amount_pattern': AmountPattern.pence.name,
                    'amount_pence': 0,
                    'amount_exact': '',
                },
                {
                    'amount__endswith': '00',
                },
            ),

            # amount_pattern == 'not_integral'
            (
                {
                    'amount_pattern': AmountPattern.not_integral.name,
                    'amount_exact': '£100',
                    'amount_pence': '99',
                },
                {
                    'page': 1,
                    'amount_pattern': AmountPattern.not_integral.name,
                    'amount_pence': '',
                    'amount_exact': '',
                },
                {
                    'exclude_amount__endswith': '00',
                },
            ),

            # amount_pattern == 'not_multiple_5'
            (
                {
                    'amount_pattern': AmountPattern.not_multiple_5.name,
                    'amount_exact': '£100',
                    'amount_pence': '99',
                },
                {
                    'page': 1,
                    'amount_pattern': AmountPattern.not_multiple_5.name,
                    'amount_pence': '',
                    'amount_exact': '',
                },
                {
                    'exclude_amount__regex': '(500|000)$',
                },
            ),

            # amount_pattern == 'not_multiple_10'
            (
                {
                    'amount_pattern': AmountPattern.not_multiple_10.name,
                    'amount_exact': '£100',
                    'amount_pence': '99',
                },
                {
                    'page': 1,
                    'amount_pattern': AmountPattern.not_multiple_10.name,
                    'amount_pence': '',
                    'amount_exact': '',
                },
                {
                    'exclude_amount__endswith': '000',
                },
            ),

            # amount_pattern == £100 or more
            (
                {
                    'amount_pattern': AmountPattern.gte_100.name,
                    'amount_exact': '£100',
                    'amount_pence': '99',
                },
                {
                    'page': 1,
                    'amount_pattern': AmountPattern.gte_100.name,
                    'amount_pence': '',
                    'amount_exact': '',
                },
                {
                    'amount__gte': '10000',
                },
            ),

            # no amount_pattern
            (
                {
                    'amount_pattern': '',
                    'amount_exact': '£100',
                    'amount_pence': '99',
                },
                {
                    'page': 1,
                    'amount_pattern': '',
                    'amount_pence': '',
                    'amount_exact': '',
                },
                {},
            ),
        ]

        for data, expected_cleaned_data, expected_api_request_params in scenarios:
            form = MyAmountSearchForm(
                mock.MagicMock(),
                data=data,
            )

            self.assertTrue(form.is_valid())
            self.assertDictEqual(
                form.cleaned_data,
                expected_cleaned_data,
            )
            self.assertDictEqual(
                form.get_api_request_params(),
                expected_api_request_params,
            )

    def test_invalid(self):
        """
        Test validation errors.
        """
        scenarios = [
            ValidationScenario(
                {'amount_pattern': AmountPattern.exact.name},
                {'amount_exact': ['This field is required for the selected amount pattern.']},
            ),
            ValidationScenario(
                {'amount_pattern': AmountPattern.pence.name},
                {'amount_pence': ['This field is required for the selected amount pattern.']},
            ),
            ValidationScenario(
                {
                    'amount_pattern': AmountPattern.pence.name,
                    'amount_pence': -1,
                },
                {'amount_pence': ['Ensure this value is greater than or equal to 0.']},
            ),
            ValidationScenario(
                {
                    'amount_pattern': AmountPattern.pence.name,
                    'amount_pence': 100,
                },
                {'amount_pence': ['Ensure this value is less than or equal to 99.']},
            ),
            ValidationScenario(
                {'amount_pattern': 'invalid'},
                {'amount_pattern': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
            ValidationScenario(
                {
                    'amount_pattern': AmountPattern.exact.name,
                    'amount_exact': '$100',
                },
                {'amount_exact': ['Invalid amount.']},
            ),
            ValidationScenario(
                {
                    'amount_pattern': AmountPattern.exact.name,
                    'amount_exact': '£100.0.0',
                },
                {'amount_exact': ['Invalid amount.']},
            ),
            ValidationScenario(
                {
                    'amount_pattern': AmountPattern.exact.name,
                    'amount_exact': 'one',
                },
                {'amount_exact': ['Invalid amount.']},
            ),
        ]

        for scenario in scenarios:
            form = MyAmountSearchForm(
                mock.MagicMock(),
                data=scenario.data,
            )
            self.assertFalse(form.is_valid())
            self.assertDictEqual(form.errors, scenario.expected_errors)


class PrisonSelectorSearchFormMixinTestCase(SimpleTestCase):
    """
    Tests for the PrisonSelectorSearchFormMixin.
    """
    def setUp(self):
        super().setUp()
        self.disable_cache = mock.patch('security.models.cache')
        self.disable_cache.start().get.return_value = None

    def tearDown(self):
        self.disable_cache.stop()

    def test_valid(self):
        """
        Test valid scenarios.

        Note: prison is reset when prison_selector is not `exact`.
        """
        Scenario = namedtuple(
            'Scenario',
            [
                'user_prisons',
                'data',
                'expected_cleaned_data',
                'expected_api_request_params',
                'expected_query_string'
            ],
        )

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            scenarios = [
                # selection == user's prisons AND current user's prisons == one prison
                Scenario(
                    [SAMPLE_PRISONS[0]],
                    {
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                        'prison': [SAMPLE_PRISONS[1]['nomis_id']],
                    },
                    {
                        'page': 1,
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                        'prison': [],  # reset
                    },
                    {
                        'prison': [SAMPLE_PRISONS[0]['nomis_id']],
                    },
                    {
                        'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                    },
                ),

                # selection == user's prisons AND current user's prisons == all prisons
                Scenario(
                    [],
                    {
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                        'prison': [SAMPLE_PRISONS[1]['nomis_id']],
                    },
                    {
                        'page': 1,
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                        'prison': [],  # reset
                    },
                    {},  # expected api query params empty because we don't want to filter by any prison
                    {
                        'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                    },
                ),

                # selection == all
                Scenario(
                    [SAMPLE_PRISONS[0]],
                    {
                        'prison_selector': MyPrisonSelectorSearchForm.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE,
                        'prison': [SAMPLE_PRISONS[1]['nomis_id']],
                    },
                    {
                        'page': 1,
                        'prison_selector': MyPrisonSelectorSearchForm.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE,
                        'prison': [],  # reset
                    },
                    {},  # expected api query params empty because we don't want to filter by any prison
                    {
                        'prison_selector': [MyPrisonSelectorSearchForm.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE],
                    },
                ),

                # selection == exact
                Scenario(
                    [SAMPLE_PRISONS[0]],
                    {
                        'prison_selector': PrisonSelectorSearchFormMixin.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE,
                        'prison': [SAMPLE_PRISONS[1]['nomis_id']],
                    },
                    {
                        'page': 1,
                        'prison_selector': PrisonSelectorSearchFormMixin.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE,
                        'prison': [SAMPLE_PRISONS[1]['nomis_id']],
                    },
                    {
                        'prison': [SAMPLE_PRISONS[1]['nomis_id']],
                    },
                    {
                        'prison_selector': [PrisonSelectorSearchFormMixin.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE],
                        'prison': [SAMPLE_PRISONS[1]['nomis_id']],
                    },
                ),

            ]
            for scenario in scenarios:
                request = mock.MagicMock(
                    user=mock.MagicMock(
                        token=generate_tokens(),
                    ),
                    user_prisons=scenario.user_prisons,
                )

                form = MyPrisonSelectorSearchForm(request, data=scenario.data)

                self.assertTrue(form.is_valid())
                self.assertDictEqual(
                    form.cleaned_data,
                    scenario.expected_cleaned_data,
                )
                self.assertDictEqual(
                    form.get_api_request_params(),
                    scenario.expected_api_request_params,
                )
                self.assertDictEqual(
                    parse_qs(form.query_string),
                    scenario.expected_query_string,
                )

    def test_invalid(self):
        """
        Test validation errors.
        """
        scenarios = [
            ValidationScenario(
                {'prison_selector': PrisonSelectorSearchFormMixin.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE},
                {'prison': ['This field is required']},
            ),
            ValidationScenario(
                {
                    'prison_selector': PrisonSelectorSearchFormMixin.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE,
                    'prison': ['invalid'],
                },
                {'prison': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
            ValidationScenario(
                {'prison_selector': 'invalid'},
                {'prison_selector': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
        ]

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)

            for scenario in scenarios:
                form = MyPrisonSelectorSearchForm(
                    mock.MagicMock(),
                    data=scenario.data,
                )
                self.assertFalse(form.is_valid())
                self.assertDictEqual(form.errors, scenario.expected_errors)


class PaymentMethodSearchFormMixinTestCase(SimpleTestCase):
    """
    Tests for the PaymentMethodSearchFormMixin.
    """
    def setUp(self):
        super().setUp()
        self.disable_cache = mock.patch('security.models.cache')
        self.disable_cache.start().get.return_value = None

    def tearDown(self):
        self.disable_cache.stop()

    def test_valid(self):
        """
        Test valid scenarios.

        Note:
        account_number and sort_code are reset if payment method != bank_transfer
        card_number_last_digits is reset if payment method != online
        """
        Scenario = namedtuple(
            'Scenario',
            [
                'data',
                'expected_cleaned_data',
                'expected_api_request_params',
                'expected_query_string'
            ],
        )

        scenarios = [
            # payment method == 'Any'
            Scenario(
                {
                    'payment_method': '',
                    'account_number': '112233',
                    'sort_code': '44-55-66',
                    'card_number_last_digits': '9876',
                },
                {
                    'page': 1,
                    'payment_method': '',
                    'account_number': '',
                    'sort_code': '',
                    'card_number_last_digits': '',
                },
                {},
                {},
            ),
            # no payment method
            Scenario(
                {
                    'account_number': '112233',
                    'sort_code': '44-55-66',
                    'card_number_last_digits': '9876',
                },
                {
                    'page': 1,
                    'payment_method': '',
                    'account_number': '',
                    'sort_code': '',
                    'card_number_last_digits': '',
                },
                {},
                {},
            ),
            # bank tranfer + account number
            Scenario(
                {
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '112233',
                    'card_number_last_digits': '9876',
                },
                {
                    'page': 1,
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '112233',
                    'sort_code': '',
                    'card_number_last_digits': '',  # reset
                },
                {
                    'method': PaymentMethod.bank_transfer.name,
                    'account_number': '112233',
                },
                {
                    'payment_method': [PaymentMethod.bank_transfer.name],
                    'account_number': ['112233'],
                },
            ),
            # bank tranfer + sort code
            Scenario(
                {
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'sort_code': '44-55 66',
                    'card_number_last_digits': '9876',
                },
                {
                    'page': 1,
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '',
                    'sort_code': '445566',
                    'card_number_last_digits': '',  # reset
                },
                {
                    'method': PaymentMethod.bank_transfer.name,
                    'sort_code': '445566',
                },
                {
                    'payment_method': [PaymentMethod.bank_transfer.name],
                    'sort_code': ['445566'],
                },
            ),
            # bank tranfer + account number + sort code
            Scenario(
                {
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '112233',
                    'sort_code': '44-55 66',
                    'card_number_last_digits': '9876',
                },
                {
                    'page': 1,
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '112233',
                    'sort_code': '445566',
                    'card_number_last_digits': '',  # reset
                },
                {
                    'method': PaymentMethod.bank_transfer.name,
                    'account_number': '112233',
                    'sort_code': '445566',
                },
                {
                    'payment_method': [PaymentMethod.bank_transfer.name],
                    'account_number': ['112233'],
                    'sort_code': ['445566'],
                },
            ),
            # online + card_number_last_digits
            Scenario(
                {
                    'payment_method': PaymentMethod.online.name,
                    'account_number': '112233',
                    'sort_code': '44-55-66',
                    'card_number_last_digits': '9876',
                },
                {
                    'page': 1,
                    'payment_method': PaymentMethod.online.name,
                    'account_number': '',  # reset
                    'sort_code': '',  # reset
                    'card_number_last_digits': '9876',
                },
                {
                    'method': PaymentMethod.online.name,
                    'card_number_last_digits': '9876',
                },
                {
                    'payment_method': [PaymentMethod.online.name],
                    'card_number_last_digits': ['9876'],
                },
            ),
            # cheque
            Scenario(
                {
                    'payment_method': PaymentMethod.cheque.name,
                    'account_number': '112233',
                    'sort_code': '44-55-66',
                    'card_number_last_digits': '9876',
                },
                {
                    'page': 1,
                    'payment_method': PaymentMethod.cheque.name,
                    'account_number': '',  # reset
                    'sort_code': '',  # reset
                    'card_number_last_digits': '',  # reset
                },
                {
                    'method': PaymentMethod.cheque.name,
                },
                {
                    'payment_method': [PaymentMethod.cheque.name],
                },
            ),
        ]

        for scenario in scenarios:
            form = MyPaymentMethodSearchForm(
                mock.MagicMock(),
                data=scenario.data,
            )

            self.assertTrue(form.is_valid())
            self.assertDictEqual(
                form.cleaned_data,
                scenario.expected_cleaned_data,
            )
            self.assertDictEqual(
                form.get_api_request_params(),
                scenario.expected_api_request_params,
            )
            self.assertDictEqual(
                parse_qs(form.query_string),
                scenario.expected_query_string,
            )

    def test_invalid(self):
        """
        Test validation errors.
        """
        scenarios = [
            ValidationScenario(
                {'payment_method': 'invalid'},
                {'payment_method': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
        ]

        for scenario in scenarios:
            form = MyPaymentMethodSearchForm(
                mock.MagicMock(),
                data=scenario.data,
            )
            self.assertFalse(form.is_valid())
            self.assertDictEqual(form.errors, scenario.expected_errors)

    def test_overridden_api_mapping(self):
        """
        Test that if PAYMENT_METHOD_API_FIELDS_MAPPING if overridden, the api call uses
        the translated filter name whilst the query string keeps the original field name.
        """
        class _MyPaymentMethodSearchForm(MyPaymentMethodSearchForm):
            PAYMENT_METHOD_API_FIELDS_MAPPING = {
                'payment_method': 'api_payment_method',
                'account_number': 'api_account_number',
                'sort_code': 'api_sort_code',
                'card_number_last_digits': 'api_card_number_last_digits',
            }

        Scenario = namedtuple(
            'Scenario',
            [
                'data',
                'expected_api_request_params',
                'expected_query_string'
            ],
        )

        scenarios = [
            # bank transfer + account number + sort code
            Scenario(
                {
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '112233',
                    'sort_code': '44-55 66',
                },
                {
                    'api_payment_method': PaymentMethod.bank_transfer.name,
                    'api_account_number': '112233',
                    'api_sort_code': '445566',
                },
                {
                    'payment_method': [PaymentMethod.bank_transfer.name],
                    'account_number': ['112233'],
                    'sort_code': ['445566'],
                },
            ),
            # online + card_number_last_digits
            Scenario(
                {
                    'payment_method': PaymentMethod.online.name,
                    'card_number_last_digits': '9876',
                },
                {
                    'api_payment_method': PaymentMethod.online.name,
                    'api_card_number_last_digits': '9876',
                },
                {
                    'payment_method': [PaymentMethod.online.name],
                    'card_number_last_digits': ['9876'],
                },
            ),
        ]

        for scenario in scenarios:
            form = _MyPaymentMethodSearchForm(
                mock.MagicMock(),
                data=scenario.data,
            )
            self.assertTrue(form.is_valid())
            self.assertDictEqual(
                form.get_api_request_params(),
                scenario.expected_api_request_params,
            )
            self.assertDictEqual(
                parse_qs(form.query_string),
                scenario.expected_query_string,
            )


class SecurityFormTestCase(SimpleTestCase):
    form_class = None

    def setUp(self):
        super().setUp()
        self.user_prisons = SAMPLE_PRISONS[:1]
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens(),
            ),
            user_prisons=self.user_prisons,
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


class LegacySecurityFormTestCase(SecurityFormTestCase):
    """
    Base TestCase class for security search form V1

    TODO: delete after search V2 goes live.
    """
    def test_filtering_by_one_prison(self):
        if not self.form_class:
            return

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data=QueryDict('prison=INP', mutable=True))
        initial_ordering = form['ordering'].initial
        self.assertTrue(form.is_valid())

        expected_query_data = {
            'ordering': initial_ordering,
            'prison': ['INP'],
        }
        expected_query_string = f'ordering={initial_ordering}&prison=INP'

        self.assertDictEqual(form.get_query_data(), expected_query_data)
        self.assertEqual(form.query_string, expected_query_string)

    def test_filtering_by_many_prisons(self):
        if not self.form_class:
            return

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data=QueryDict('prison=IXB&prison=INP', mutable=True))
        initial_ordering = form['ordering'].initial
        self.assertTrue(form.is_valid())

        expected_query_data = {
            'ordering': initial_ordering,
            'prison': ['INP', 'IXB'],
        }
        expected_query_string = f'ordering={initial_ordering}&prison=INP&prison=IXB'

        self.assertDictEqual(form.get_query_data(), expected_query_data)
        self.assertEqual(form.query_string, expected_query_string)

    def test_filtering_by_many_prisons_alternate(self):
        if not self.form_class:
            return

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data=QueryDict('prison=IXB,INP,', mutable=True))
        initial_ordering = form['ordering'].initial
        self.assertTrue(form.is_valid())

        expected_query_data = {
            'ordering': initial_ordering,
            'prison': ['INP', 'IXB'],
        }
        expected_query_string = f'ordering={initial_ordering}&prison=INP&prison=IXB'

        self.assertDictEqual(form.get_query_data(), expected_query_data)
        self.assertEqual(form.query_string, expected_query_string)


class SenderFormTestCase(LegacySecurityFormTestCase):
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
            form = self.form_class(self.request, data={'page': '1'})
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
            form = self.form_class(self.request, data={'page': '1', 'ordering': '-credit_total', 'sender_name': 'Joh '})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-credit_total', 'sender_name': 'Joh'})
        self.assertEqual(form.query_string, 'ordering=-credit_total&sender_name=Joh')

    def test_sender_list_invalid_forms(self):
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())


class SenderFormV2TestCase(SecurityFormTestCase):
    """
    Tests related to the SenderFormV2.
    """

    form_class = SendersFormV2
    api_list_path = '/senders/'

    def test_blank_form(self):
        """
        Test that if no data is passed in, the default values are used instead.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(self.request, data={})
            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])

            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['0'],
                    'limit': ['20'],
                    'ordering': ['-prisoner_count'],
                    'prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                },
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 1,
                'ordering': '-prisoner_count',
                'prison': [],
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'advanced': False,
                'simple_search': '',
                'sender_name': '',
                'sender_email': '',
                'sender_postcode': '',
                'card_number_last_digits': '',
                'payment_method': '',
                'account_number': '',
                'sort_code': '',
            },
        )
        self.assertEqual(
            parse_qs(form.query_string),
            {
                'advanced': ['False'],
                'ordering': ['-prisoner_count'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
            },
        )

    def test_valid_simple_search(self):
        """
        Test that if data for a simple search is passed in, the API query string is constructed as expected.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(
                self.request,
                data={
                    'page': 2,
                    'ordering': '-credit_total',
                    'prison_selection': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    'simple_search': 'Joh',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])
            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['20'],
                    'limit': ['20'],
                    'ordering': ['-credit_total'],
                    'simple_search': ['Joh'],
                    'prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                },
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'advanced': False,
                'card_number_last_digits': '',
                'page': 2,
                'ordering': '-credit_total',
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'prison': [],
                'payment_method': '',
                'account_number': '',
                'sort_code': '',
                'sender_email': '',
                'sender_name': '',
                'sender_postcode': '',
                'simple_search': 'Joh',
            },
        )

        self.assertDictEqual(
            parse_qs(form.query_string),
            {
                'advanced': ['False'],
                'ordering': ['-credit_total'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                'simple_search': ['Joh'],
            },
        )

    def test_valid_advanced_search(self):
        """
        Test that if data for an advanced search is passed in, the API query string is constructed as expected.
        """
        scenarios = [
            # bank transfer
            (
                {  # request_data
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '123456789',
                    'sort_code': '11-22 - 33',
                    'sender_email': '',
                    'sender_postcode': '',
                },
                {  # expected_api_call_params
                    'source': [PaymentMethod.bank_transfer.name],
                    'sender_account_number': ['123456789'],
                    'sender_sort_code': ['112233'],
                },
                {  # expected_cleaned_data
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '123456789',
                    'sort_code': '112233',
                    'sender_email': '',
                    'sender_postcode': '',
                    'card_number_last_digits': '',
                },
                {  # expected_qs
                    'payment_method': [PaymentMethod.bank_transfer.name],
                    'account_number': ['123456789'],
                    'sort_code': ['112233'],
                },
            ),

            # debit card
            (
                {  # request_data
                    'payment_method': PaymentMethod.online.name,
                    'sender_email': 'john@example.com',
                    'sender_postcode': 'SW1A 1a-a',
                    'card_number_last_digits': '1234',
                    'account_number': '',
                    'sort_code': '',
                },
                {  # expected_api_call_params
                    'source': [PaymentMethod.online.name],
                    'sender_email': ['john@example.com'],
                    'sender_postcode': ['SW1A1aa'],
                    'card_number_last_digits': ['1234'],
                },
                {  # expected_cleaned_data
                    'payment_method': PaymentMethod.online.name,
                    'sender_email': 'john@example.com',
                    'sender_postcode': 'SW1A1aa',
                    'card_number_last_digits': '1234',
                    'account_number': '',
                    'sort_code': '',
                },
                {  # expected_qs
                    'payment_method': [PaymentMethod.online.name],
                    'sender_email': ['john@example.com'],
                    'sender_postcode': ['SW1A1aa'],
                    'card_number_last_digits': ['1234'],
                },
            ),
        ]

        for request_data, expected_api_call_params, expected_cleaned_data, expected_qs in scenarios:
            with responses.RequestsMock() as rsps:
                mock_prison_response(rsps)
                mock_empty_response(rsps, self.api_list_path)

                form = self.form_class(
                    self.request,
                    data={
                        'page': 2,
                        'ordering': '-credit_total',
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                        'advanced': True,
                        'sender_name': 'John Doe',

                        **request_data,
                    },
                )

                self.assertTrue(form.is_valid())
                self.assertListEqual(form.get_object_list(), [])

                api_call_made = rsps.calls[-1].request.url
                self.assertDictEqual(
                    parse_qs(api_call_made.split('?', 1)[1]),
                    {
                        'offset': ['20'],
                        'limit': ['20'],
                        'ordering': ['-credit_total'],
                        'prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                            prison['nomis_id']
                            for prison in self.user_prisons
                        ],
                        'sender_name': ['John Doe'],

                        **expected_api_call_params,
                    },
                )

            self.assertDictEqual(
                form.cleaned_data,
                {
                    'simple_search': '',
                    'advanced': True,
                    'page': 2,
                    'ordering': '-credit_total',
                    'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    'prison': [],
                    'sender_name': 'John Doe',

                    **expected_cleaned_data,
                },
            )

            self.assertDictEqual(
                parse_qs(form.query_string),
                {
                    'ordering': ['-credit_total'],
                    'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                    'advanced': ['True'],
                    'sender_name': ['John Doe'],

                    **expected_qs,
                },
            )

    def test_invalid(self):
        """
        Test validation errors.
        """
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
                {
                    'prison_selector': self.form_class.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE,
                    'prison': ['invalid'],
                },
                {'prison': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
            ValidationScenario(
                {
                    'payment_method': PaymentMethod.online.name,
                    'card_number_last_digits': '12345',
                },
                {'card_number_last_digits': ['You’ve entered too many characters']},
            ),
            ValidationScenario(
                {
                    'payment_method': '',
                    'sender_email': 'john@example.com',
                    'sender_postcode': 'SW1A1AA',
                },
                {
                    'sender_email': ['Only available for debit card payments.'],
                    'sender_postcode': ['Only available for debit card payments.'],
                },
            ),
            ValidationScenario(
                {
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'sender_email': 'john@example.com',
                    'sender_postcode': 'SW1A1AA',
                },
                {
                    'sender_email': ['Only available for debit card payments.'],
                    'sender_postcode': ['Only available for debit card payments.'],
                },
            ),
        ]

        for scenario in scenarios:
            with responses.RequestsMock() as rsps:
                mock_prison_response(rsps)
                form = self.form_class(self.request, data=scenario.data)
            self.assertFalse(form.is_valid())
            self.assertDictEqual(form.errors, scenario.expected_errors)


class PrisonerFormTestCase(LegacySecurityFormTestCase):
    """
    TODO: delete after search V2 goes live.
    """
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
            form = self.form_class(self.request, data={'page': '1'})
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
            form = self.form_class(
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
            form = self.form_class(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())


class PrisonerFormV2TestCase(SecurityFormTestCase):
    """
    Tests related to the PrisonersFormV2.
    """
    form_class = PrisonersFormV2
    api_list_path = '/prisoners/'

    def test_blank_form(self):
        """
        Test that if no data is passed in, the default values are used instead.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(self.request, data={})
            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])

            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['0'],
                    'limit': ['20'],
                    'ordering': ['-sender_count'],
                    'current_prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                },
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 1,
                'ordering': '-sender_count',
                'prison': [],
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'simple_search': '',
                'advanced': False,
                'prisoner_name': '',
                'prisoner_number': '',
            },
        )
        self.assertEqual(
            parse_qs(form.query_string),
            {
                'advanced': ['False'],
                'ordering': ['-sender_count'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
            },
        )

    def test_valid_simple_search(self):
        """
        Test that if data for a simple search is passed in, the API query string is constructed as expected.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(
                self.request,
                data={
                    'page': 2,
                    'ordering': '-credit_total',
                    'prison_selection': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    'simple_search': 'Joh',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])
            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['20'],
                    'limit': ['20'],
                    'ordering': ['-credit_total'],
                    'simple_search': ['Joh'],
                    'current_prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                },
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'advanced': False,
                'page': 2,
                'ordering': '-credit_total',
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'prison': [],
                'simple_search': 'Joh',
                'prisoner_name': '',
                'prisoner_number': '',
            },
        )

        self.assertDictEqual(
            parse_qs(form.query_string),
            {
                'advanced': ['False'],
                'ordering': ['-credit_total'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                'simple_search': ['Joh'],
            },
        )

    def test_valid_advanced_search(self):
        """
        Test that if data for an advanced search is passed in, the API query string is constructed as expected.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(
                self.request,
                data={
                    'page': 2,
                    'ordering': '-credit_total',
                    'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    'advanced': True,
                    'prisoner_name': 'John Doe',
                    'prisoner_number': 'a2624ae',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])
            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['20'],
                    'limit': ['20'],
                    'ordering': ['-credit_total'],
                    'current_prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                    'prisoner_name': ['John Doe'],
                    'prisoner_number': ['A2624AE'],
                }
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'advanced': True,
                'page': 2,
                'ordering': '-credit_total',
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'prison': [],
                'simple_search': '',
                'prisoner_name': 'John Doe',
                'prisoner_number': 'A2624AE',
            },
        )

        self.assertDictEqual(
            parse_qs(form.query_string),
            {
                'ordering': ['-credit_total'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                'advanced': ['True'],
                'prisoner_name': ['John Doe'],
                'prisoner_number': ['A2624AE'],
            }
        )

    def test_invalid(self):
        """
        Test validation errors.
        """
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
                {
                    'prison_selector': self.form_class.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE,
                    'prison': ['invalid'],
                },
                {'prison': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
            ValidationScenario(
                {'prisoner_number': 'invalid'},
                {'prisoner_number': ['Invalid prisoner number.']},
            ),
        ]

        for scenario in scenarios:
            with responses.RequestsMock() as rsps:
                mock_prison_response(rsps)
                form = self.form_class(self.request, data=scenario.data)
            self.assertFalse(form.is_valid())
            self.assertDictEqual(form.errors, scenario.expected_errors)


class CreditFormTestCase(LegacySecurityFormTestCase):
    """
    TODO: delete after search V2 goes live.
    """
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
            form = self.form_class(self.request, data={'page': '1'})
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
            form = self.form_class(
                self.request,
                data={'page': '1', 'ordering': '-amount', 'received_at__gte': '26/5/2016'},
            )
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
        self.assertDictEqual(form.get_query_data(), {'ordering': '-amount', 'received_at__gte': received_at__gte})
        self.assertEqual(form.query_string, 'ordering=-amount&received_at__gte=2016-05-26')

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '1', 'amount_pattern': 'not_integral'})
        self.assertTrue(form.is_valid(), msg=form.errors.as_text())
        self.assertDictEqual(form.get_query_data(), {'ordering': '-received_at', 'exclude_amount__endswith': '00'})
        self.assertDictEqual(form.get_query_data(allow_parameter_manipulation=False),
                             {'ordering': '-received_at', 'amount_pattern': 'not_integral'})
        self.assertEqual(form.query_string, 'ordering=-received_at&amount_pattern=not_integral')

    def test_credits_list_invalid_forms(self):
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())


class CreditFormV2TestCase(SecurityFormTestCase):
    """
    Tests related to the CreditFormV2.
    """
    form_class = CreditsFormV2
    api_list_path = '/credits/'

    def test_blank_form(self):
        """
        Test that if no data is passed in, the default values are used instead.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(self.request, data={})
            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])

            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['0'],
                    'limit': ['20'],
                    'ordering': ['-received_at'],
                    'prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                },
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 1,
                'ordering': '-received_at',
                'prison': [],
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'simple_search': '',
                'advanced': False,
                'amount_pattern': '',
                'amount_exact': '',
                'amount_pence': '',
                'prisoner_name': '',
                'prisoner_number': '',
                'sender_name': '',
                'sender_email': '',
                'sender_postcode': '',
                'sender_ip_address': '',
                'card_number_last_digits': '',
                'payment_method': '',
                'account_number': '',
                'sort_code': '',
                'received_at__gte': None,
                'received_at__lt': None,
            },
        )
        self.assertEqual(
            parse_qs(form.query_string),
            {
                'advanced': ['False'],
                'ordering': ['-received_at'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
            },
        )

    def test_valid_simple_search(self):
        """
        Test that if data for a simple search is passed in, the API query string is constructed as expected.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(
                self.request,
                data={
                    'page': 2,
                    'ordering': '-amount',
                    'prison_selection': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    'simple_search': 'Joh',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])
            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['20'],
                    'limit': ['20'],
                    'ordering': ['-amount'],
                    'simple_search': ['Joh'],
                    'prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                },
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'advanced': False,
                'page': 2,
                'ordering': '-amount',
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'prison': [],
                'simple_search': 'Joh',
                'amount_pattern': '',
                'amount_exact': '',
                'amount_pence': '',
                'prisoner_name': '',
                'prisoner_number': '',
                'sender_name': '',
                'sender_email': '',
                'sender_postcode': '',
                'sender_ip_address': '',
                'card_number_last_digits': '',
                'payment_method': '',
                'account_number': '',
                'sort_code': '',
                'received_at__gte': None,
                'received_at__lt': None,
            },
        )

        self.assertDictEqual(
            parse_qs(form.query_string),
            {
                'advanced': ['False'],
                'ordering': ['-amount'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                'simple_search': ['Joh'],
            },
        )

    def test_valid_advanced_search(self):
        """
        Test that if data for an advanced search is passed in, the API query string is constructed as expected.
        """
        scenarios = [
            (
                {  # request_data
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '123456789',
                    'sort_code': '11-22 - 33',
                    'sender_email': '',
                    'sender_postcode': '',
                    'sender_ip_address': '',
                },
                {  # expected_api_call_params
                    'source': [PaymentMethod.bank_transfer.name],
                    'sender_account_number': ['123456789'],
                    'sender_sort_code': ['112233'],
                },
                {  # expected_cleaned_data
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '123456789',
                    'sort_code': '112233',
                    'sender_email': '',
                    'sender_postcode': '',
                    'sender_ip_address': '',
                    'card_number_last_digits': '',
                },
                {  # expected_qs
                    'payment_method': [PaymentMethod.bank_transfer.name],
                    'account_number': ['123456789'],
                    'sort_code': ['112233'],
                },
            ),
            (
                {  # request_data
                    'payment_method': PaymentMethod.online.name,
                    'sender_email': 'johndoe',
                    'sender_postcode': 'SW1A 1a-a',
                    'sender_ip_address': '127.0.0.1',
                    'card_number_last_digits': '1234',
                    'account_number': '',
                    'sort_code': '',
                },
                {  # expected_api_call_params
                    'source': [PaymentMethod.online.name],
                    'sender_email': ['johndoe'],
                    'sender_postcode': ['SW1A1aa'],
                    'sender_ip_address': ['127.0.0.1'],
                    'card_number_last_digits': ['1234'],
                },
                {  # expected_cleaned_data
                    'payment_method': PaymentMethod.online.name,
                    'sender_email': 'johndoe',
                    'sender_postcode': 'SW1A1aa',
                    'sender_ip_address': '127.0.0.1',
                    'card_number_last_digits': '1234',
                    'account_number': '',
                    'sort_code': '',
                },
                {  # expected_qs
                    'payment_method': [PaymentMethod.online.name],
                    'sender_email': ['johndoe'],
                    'sender_postcode': ['SW1A1aa'],
                    'sender_ip_address': ['127.0.0.1'],
                    'card_number_last_digits': ['1234'],
                },
            ),
        ]

        for request_data, expected_api_call_params, expected_cleaned_data, expected_qs in scenarios:
            with responses.RequestsMock() as rsps:
                mock_prison_response(rsps)
                mock_empty_response(rsps, self.api_list_path)

                form = self.form_class(
                    self.request,
                    data={
                        'page': 2,
                        'ordering': '-amount',
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                        'advanced': True,
                        'amount_pattern': AmountPattern.exact.name,
                        'amount_exact': '100.00',
                        'amount_pence': '',
                        'prisoner_name': 'Jane Doe',
                        'prisoner_number': 'a2624ae',
                        'sender_name': 'John Doe',
                        'received_at__gte_0': '1',
                        'received_at__gte_1': '2',
                        'received_at__gte_2': '2000',
                        'received_at__lt_0': '10',
                        'received_at__lt_1': '3',
                        'received_at__lt_2': '2000',

                        **request_data,
                    },
                )

                self.assertTrue(form.is_valid())
                self.assertListEqual(form.get_object_list(), [])

                api_call_made = rsps.calls[-1].request.url
                self.assertDictEqual(
                    parse_qs(api_call_made.split('?', 1)[1]),
                    {
                        'offset': ['20'],
                        'limit': ['20'],
                        'ordering': ['-amount'],
                        'prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                            prison['nomis_id']
                            for prison in self.user_prisons
                        ],
                        'amount': ['10000'],
                        'prisoner_name': ['Jane Doe'],
                        'prisoner_number': ['A2624AE'],
                        'sender_name': ['John Doe'],
                        'received_at__gte': ['2000-02-01'],
                        'received_at__lt': ['2000-03-11'],

                        **expected_api_call_params,
                    },
                )

            self.assertDictEqual(
                form.cleaned_data,
                {
                    'advanced': True,
                    'page': 2,
                    'ordering': '-amount',
                    'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    'prison': [],
                    'simple_search': '',
                    'amount_pattern': AmountPattern.exact.name,
                    'amount_exact': '100.00',
                    'amount_pence': '',
                    'prisoner_name': 'Jane Doe',
                    'prisoner_number': 'A2624AE',
                    'sender_name': 'John Doe',
                    'received_at__gte': datetime.date(2000, 2, 1),
                    'received_at__lt': datetime.date(2000, 3, 10),

                    **expected_cleaned_data,
                },
            )

            # make sure the values for dates are split
            self.assertDictEqual(
                parse_qs(form.query_string),
                {
                    'ordering': ['-amount'],
                    'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                    'amount_pattern': ['exact'],
                    'amount_exact': ['100.00'],
                    'advanced': ['True'],
                    'sender_name': ['John Doe'],
                    'prisoner_name': ['Jane Doe'],
                    'prisoner_number': ['A2624AE'],
                    'received_at__gte_0': ['1'],
                    'received_at__gte_1': ['2'],
                    'received_at__gte_2': ['2000'],
                    'received_at__lt_0': ['10'],
                    'received_at__lt_1': ['3'],
                    'received_at__lt_2': ['2000'],

                    **expected_qs,
                }
            )

    def test_invalid(self):
        """
        Test validation errors.
        """
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
                {
                    'prison_selector': self.form_class.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE,
                    'prison': ['invalid'],
                },
                {'prison': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
            ValidationScenario(
                {'prisoner_number': 'invalid'},
                {'prisoner_number': ['Invalid prisoner number.']},
            ),
            ValidationScenario(
                {
                    'payment_method': PaymentMethod.online.name,
                    'card_number_last_digits': '12345',
                },
                {'card_number_last_digits': ['You’ve entered too many characters']},
            ),
            ValidationScenario(
                {'sender_ip_address': '256.0.0.1'},
                {'sender_ip_address': ['Enter a valid IPv4 address.']},
            ),
            ValidationScenario(
                {
                    'received_at__gte_0': '2',
                    'received_at__gte_1': '2',
                    'received_at__gte_2': '2000',
                    'received_at__lt_0': '1',
                    'received_at__lt_1': '2',
                    'received_at__lt_2': '2000',
                },
                {'received_at__lt': ['Must be after the start date.']},
            ),
            ValidationScenario(
                {
                    'received_at__gte_0': '32',
                    'received_at__gte_1': '13',
                    'received_at__gte_2': '1111',
                },
                {
                    'received_at__gte': [
                        '‘Day’ should be between 1 and 31',
                        '‘Month’ should be between 1 and 12',
                        '‘Year’ should be between 1900 and 2019',
                    ],
                },
            ),
            ValidationScenario(
                {
                    'payment_method': '',
                    'sender_email': 'john@example.com',
                    'sender_postcode': 'SW1A1AA',
                    'sender_ip_address': '127.0.0.1',
                },
                {
                    'sender_email': ['Only available for debit card payments.'],
                    'sender_postcode': ['Only available for debit card payments.'],
                    'sender_ip_address': ['Only available for debit card payments.'],
                },
            ),
            ValidationScenario(
                {
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'sender_email': 'john@example.com',
                    'sender_postcode': 'SW1A1AA',
                    'sender_ip_address': '127.0.0.1',
                },
                {
                    'sender_email': ['Only available for debit card payments.'],
                    'sender_postcode': ['Only available for debit card payments.'],
                    'sender_ip_address': ['Only available for debit card payments.'],
                },
            ),
        ]

        for scenario in scenarios:
            with responses.RequestsMock() as rsps:
                mock_prison_response(rsps)
                form = self.form_class(self.request, data=scenario.data)
            self.assertFalse(form.is_valid())
            self.assertDictEqual(form.errors, scenario.expected_errors)


class DisbursementFormTestCase(LegacySecurityFormTestCase):
    """
    TODO: delete after search V2 goes live.
    """
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
            form = self.form_class(self.request, data={'page': '1'})
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
            form = self.form_class(
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
            form = self.form_class(self.request, data={'page': '1', 'amount_pattern': 'not_integral'})
        self.assertTrue(form.is_valid(), msg=form.errors.as_text())
        self.assertDictEqual(form.get_query_data(), {'ordering': '-created', 'exclude_amount__endswith': '00'})
        self.assertDictEqual(form.get_query_data(allow_parameter_manipulation=False),
                             {'ordering': '-created', 'amount_pattern': 'not_integral'})
        self.assertEqual(form.query_string, 'ordering=-created&amount_pattern=not_integral')

    def test_disbursements_list_invalid_forms(self):
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '0'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '1', 'ordering': 'prison'})
        self.assertFalse(form.is_valid())

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data={'page': '1', 'prison': 'ABC'})
        self.assertFalse(form.is_valid())


class DisbursementFormV2TestCase(SecurityFormTestCase):
    """
    TODO: delete after search V2 goes live.
    """
    form_class = DisbursementsFormV2
    api_list_path = '/disbursements/'

    def test_blank_form(self):
        """
        Test that if no data is passed in, the default values are used instead.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(self.request, data={})
            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])

            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['0'],
                    'limit': ['20'],
                    'ordering': ['-created'],
                    'prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                },
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 1,
                'ordering': '-created',
                'prison': [],
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'simple_search': '',
                'advanced': False,
                'amount_exact': '',
                'amount_pattern': '',
                'amount_pence': '',
                'recipient_name': '',
                'recipient_email': '',
                'postcode': '',
                'created__gte': None,
                'created__lt': None,
                'payment_method': '',
                'account_number': '',
                'card_number_last_digits': '',
                'sort_code': '',
                'prisoner_name': '',
                'prisoner_number': '',
                'invoice_number': '',
            },
        )
        self.assertEqual(
            parse_qs(form.query_string),
            {
                'advanced': ['False'],
                'ordering': ['-created'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
            },
        )

    def test_valid_simple_search(self):
        """
        Test that if data for a simple search is passed in, the API query string is constructed as expected.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(
                self.request,
                data={
                    'page': 2,
                    'ordering': '-amount',
                    'prison_selection': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    'simple_search': 'Joh',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])
            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['20'],
                    'limit': ['20'],
                    'ordering': ['-amount'],
                    'simple_search': ['Joh'],
                    'prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                },
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'advanced': False,
                'page': 2,
                'ordering': '-amount',
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'prison': [],
                'simple_search': 'Joh',
                'amount_exact': '',
                'amount_pattern': '',
                'amount_pence': '',
                'recipient_name': '',
                'recipient_email': '',
                'postcode': '',
                'created__gte': None,
                'created__lt': None,
                'payment_method': '',
                'account_number': '',
                'sort_code': '',
                'card_number_last_digits': '',
                'prisoner_name': '',
                'prisoner_number': '',
                'invoice_number': '',
            },
        )

        self.assertDictEqual(
            parse_qs(form.query_string),
            {
                'advanced': ['False'],
                'ordering': ['-amount'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                'simple_search': ['Joh'],
            },
        )

    def test_valid_advanced_search(self):
        """
        Test that if data for an advanced search is passed in, the API query string is constructed as expected.
        """
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(
                self.request,
                data={
                    'page': 2,
                    'ordering': '-amount',
                    'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    'advanced': True,
                    'amount_pattern': AmountPattern.exact.name,
                    'amount_exact': '100.00',
                    'amount_pence': '',
                    'recipient_name': 'John Doe',
                    'recipient_email': 'johndoe',
                    'postcode': 'SW1A 1a-a',
                    'created__gte_0': '1',
                    'created__gte_1': '2',
                    'created__gte_2': '2000',
                    'created__lt_0': '10',
                    'created__lt_1': '3',
                    'created__lt_2': '2000',
                    'payment_method': PaymentMethod.bank_transfer.name,
                    'account_number': '123456789',
                    'sort_code': '11-22 - 33',
                    'prisoner_name': 'Jane Doe',
                    'prisoner_number': 'a2624ae',
                    'invoice_number': 'PMD1000052',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])

            api_call_made = rsps.calls[-1].request.url
            self.assertDictEqual(
                parse_qs(api_call_made.split('?', 1)[1]),
                {
                    'offset': ['20'],
                    'limit': ['20'],
                    'ordering': ['-amount'],
                    'prison': [  # PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE expands into user prisons
                        prison['nomis_id']
                        for prison in self.user_prisons
                    ],
                    'amount': ['10000'],
                    'recipient_name': ['John Doe'],
                    'recipient_email': ['johndoe'],
                    'postcode': ['SW1A1aa'],
                    'created__gte': ['2000-02-01'],
                    'created__lt': ['2000-03-11'],
                    'method': [PaymentMethod.bank_transfer.name],
                    'account_number': ['123456789'],
                    'sort_code': ['112233'],
                    'prisoner_name': ['Jane Doe'],
                    'prisoner_number': ['A2624AE'],
                    'invoice_number': ['PMD1000052'],
                },
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'advanced': True,
                'page': 2,
                'ordering': '-amount',
                'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                'prison': [],
                'simple_search': '',
                'amount_pattern': AmountPattern.exact.name,
                'amount_exact': '100.00',
                'amount_pence': '',
                'recipient_name': 'John Doe',
                'recipient_email': 'johndoe',
                'postcode': 'SW1A1aa',
                'created__gte': datetime.date(2000, 2, 1),
                'created__lt': datetime.date(2000, 3, 10),
                'payment_method': PaymentMethod.bank_transfer.name,
                'account_number': '123456789',
                'sort_code': '112233',
                'card_number_last_digits': '',
                'prisoner_name': 'Jane Doe',
                'prisoner_number': 'A2624AE',
                'invoice_number': 'PMD1000052',
            },
        )

        # make sure the values for dates are split
        self.assertDictEqual(
            parse_qs(form.query_string),
            {
                'ordering': ['-amount'],
                'prison_selector': [PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE],
                'amount_pattern': ['exact'],
                'amount_exact': ['100.00'],
                'advanced': ['True'],
                'recipient_name': ['John Doe'],
                'recipient_email': ['johndoe'],
                'postcode': ['SW1A1aa'],
                'created__gte_0': ['1'],
                'created__gte_1': ['2'],
                'created__gte_2': ['2000'],
                'created__lt_0': ['10'],
                'created__lt_1': ['3'],
                'created__lt_2': ['2000'],
                'payment_method': [PaymentMethod.bank_transfer.name],
                'account_number': ['123456789'],
                'sort_code': ['112233'],
                'prisoner_name': ['Jane Doe'],
                'prisoner_number': ['A2624AE'],
                'invoice_number': ['PMD1000052'],
            }
        )

    def test_invalid(self):
        """
        Test validation errors.
        """
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
                {
                    'prison_selector': self.form_class.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE,
                    'prison': ['invalid'],
                },
                {'prison': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
            ValidationScenario(
                {'prisoner_number': 'invalid'},
                {'prisoner_number': ['Invalid prisoner number.']},
            ),
            ValidationScenario(
                {
                    'created__gte_0': '2',
                    'created__gte_1': '2',
                    'created__gte_2': '2000',
                    'created__lt_0': '1',
                    'created__lt_1': '2',
                    'created__lt_2': '2000',
                },
                {'created__lt': ['Must be after the start date.']},
            ),
            ValidationScenario(
                {
                    'created__gte_0': '32',
                    'created__gte_1': '13',
                    'created__gte_2': '1111',
                },
                {
                    'created__gte': [
                        '‘Day’ should be between 1 and 31',
                        '‘Month’ should be between 1 and 12',
                        '‘Year’ should be between 1900 and 2019',
                    ],
                },
            ),
        ]

        for scenario in scenarios:
            with responses.RequestsMock() as rsps:
                mock_prison_response(rsps)
                form = self.form_class(self.request, data=scenario.data)
            self.assertFalse(form.is_valid())
            self.assertDictEqual(form.errors, scenario.expected_errors)


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
