import datetime
from collections import namedtuple
from unittest import mock
from urllib.parse import parse_qs

from django import forms
from django.test import SimpleTestCase
from mtp_common.auth.test_utils import generate_tokens
import responses

from security.forms.object_base import AmountPattern, SecurityForm
from security.forms.object_list import (
    AmountSearchFormMixin,
    CreditsForm,
    DisbursementsForm,
    PaymentMethodSearchFormMixin,
    PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
    PrisonersForm,
    PrisonSelectorSearchFormMixin,
    SendersForm,
)
from security.models import PaymentMethod
from security.tests import api_url, mock_empty_response

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


class MyAmountSearchForm(AmountSearchFormMixin, SecurityForm):
    """
    SecurityForm used to test AmountSearchFormMixin.
    """


class MyPrisonSelectorSearchForm(PrisonSelectorSearchFormMixin, SecurityForm):
    """
    SecurityForm used to test PrisonSelectorSearchFormMixin.
    """
    simple_search = forms.CharField(required=False)


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
                        'simple_search': '',
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
                        'simple_search': '',
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
                        'simple_search': '',
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
                        'simple_search': '',
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

    def test_all_prisons_simple_search_shoud_not_be_allowed(self):
        """
        Test that the allow_all_prisons_simple_search method returns False if:

        - the form was not submitted
        - a simple search was not performed
        - the search term is empty
        - the current user's prisons value is 'all'
        """
        # case of form not submitted
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)

            form = MyPrisonSelectorSearchForm(mock.MagicMock())
            self.assertFalse(form.allow_all_prisons_simple_search())

        # cases of form submitted
        Scenario = namedtuple(
            'Scenario',
            [
                'user_prisons',
                'data',
            ],
        )

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            scenarios = [
                # selection == user's prisons AND current user's prisons == one prison AND no simple search term used
                Scenario(
                    [SAMPLE_PRISONS[0]],
                    {
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    },
                ),

                # selection == user's prisons AND current user's prisons == one prison AND
                # empty simple search term used
                Scenario(
                    [SAMPLE_PRISONS[0]],
                    {
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                        'simple_search': '',
                    },
                ),

                # selection == user's prisons AND current user's prisons == all prison AND
                # non-empty simple search term used
                Scenario(
                    [],
                    {
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                        'simple_search': 'term',
                    },
                ),

                # selection == all AND current user's prisons == one prison AND
                # non-empty simple search term used
                Scenario(
                    [SAMPLE_PRISONS[0]],
                    {
                        'prison_selector': form.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE,
                        'simple_search': 'term',
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
                self.assertFalse(form.allow_all_prisons_simple_search())

    def test_all_prisons_simple_search_allowed(self):
        """
        Test that the allow_all_prisons_simple_search method returns True if a simple search
        was made with a non-empty search term and the current user's prisons value is not 'all'.
        """
        request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens(),
            ),
            user_prisons=[SAMPLE_PRISONS[0]],
        )

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)

            form = MyPrisonSelectorSearchForm(
                request,
                data={
                    'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                    'simple_search': 'term',
                },
            )

        self.assertTrue(form.is_valid())
        self.assertTrue(form.allow_all_prisons_simple_search())

    def test_was_all_prisons_simple_search_used_false(self):
        """
        Test that the was_all_prisons_simple_search_used method returns False in any
        of the following cases:

        - the form was not submitted
        - a simple search was not performed
        - the search term is empty
        - the prison selection query param is not 'all'
        - the user's prisons value is 'all'
        """
        # case of form not submitted
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)

            form = MyPrisonSelectorSearchForm(mock.MagicMock())
            self.assertFalse(form.was_all_prisons_simple_search_used())

        # cases of form submitted
        Scenario = namedtuple(
            'Scenario',
            [
                'user_prisons',
                'data',
            ],
        )

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            scenarios = [
                # selection == all prisons AND current user's prisons == one prison AND no simple search term used
                Scenario(
                    [SAMPLE_PRISONS[0]],
                    {
                        'prison_selector': form.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE,
                    },
                ),

                # selection == all prisons AND current user's prisons == one prison AND
                # empty simple search term used
                Scenario(
                    [SAMPLE_PRISONS[0]],
                    {
                        'prison_selector': form.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE,
                        'simple_search': '',
                    },
                ),

                # selection == all prisons AND current user's prisons == all prison AND
                # non-empty simple search term used
                Scenario(
                    [],
                    {
                        'prison_selector': form.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE,
                        'simple_search': 'term',
                    },
                ),

                # selection == user's prisons AND current user's prisons == one prison AND
                # non-empty simple search term used
                Scenario(
                    [SAMPLE_PRISONS[0]],
                    {
                        'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
                        'simple_search': 'term',
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
                self.assertFalse(form.was_all_prisons_simple_search_used())

    def test_was_all_prisons_simple_search_used_true(self):
        """
        Test that the was_all_prisons_simple_search_used method returns True if
        a simple search with a non-empty search term was performed, the current user's prisons value
        is not 'all' and the prison selector query param is 'all'.
        """
        request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens(),
            ),
            user_prisons=[SAMPLE_PRISONS[0]],
        )

        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)

            form = MyPrisonSelectorSearchForm(
                request,
                data={
                    'prison_selector': MyPrisonSelectorSearchForm.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE,
                    'simple_search': 'term',
                },
            )

        self.assertTrue(form.is_valid())
        self.assertTrue(form.was_all_prisons_simple_search_used())


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


class SenderFormTestCase(SecurityFormTestCase):
    """
    Tests related to the SenderForm
    """

    form_class = SendersForm
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


class PrisonerFormTestCase(SecurityFormTestCase):
    """
    Tests related to the PrisonersForm
    """
    form_class = PrisonersForm
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


class CreditFormTestCase(SecurityFormTestCase):
    """
    Tests related to the CreditForm
    """
    form_class = CreditsForm
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
                        f'‘Year’ should be between 1900 and {datetime.date.today().year}',
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


class DisbursementFormTestCase(SecurityFormTestCase):
    """
    Tests related to the DisbursementsForm
    """
    form_class = DisbursementsForm
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
                        f'‘Year’ should be between 1900 and {datetime.date.today().year}',
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
