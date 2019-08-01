import datetime
from urllib.parse import parse_qs

import responses

from security.forms.disbursements import DisbursementsForm, DisbursementsFormV2
from security.tests.utils import mock_empty_response, mock_prison_response
from security.tests.forms.test_base import SecurityFormTestCase, ValidationScenario


class DisbursementFormTestCase(SecurityFormTestCase):
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
            self.assertEqual(
                parse_qs(rsps.calls[-1].request.url.split('?', 1)[1]),
                parse_qs('offset=0&limit=20&ordering=-created'),
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 1,
                'ordering': '-created',
                'prison': [],
                'simple_search': '',
            },
        )
        self.assertDictEqual(
            form.get_query_data(),
            {'ordering': '-created'},
        )
        self.assertEqual(
            form.query_string,
            'ordering=-created',
        )

    def test_valid(self):
        """
        Test that if data is passed in, the API query string is constructed as expected.
        """
        with responses.RequestsMock() as rsps:
            prisons = mock_prison_response(rsps)
            mock_empty_response(rsps, self.api_list_path)

            form = self.form_class(
                self.request,
                data={
                    'page': 2,
                    'ordering': '-amount',
                    'prison': [
                        prisons[0]['nomis_id'],
                    ],
                    'simple_search': 'Joh',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])
            self.assertDictEqual(
                parse_qs(rsps.calls[-1].request.url.split('?', 1)[1]),
                parse_qs('offset=20&limit=20&ordering=-amount&prison=IXB&simple_search=Joh'),
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 2,
                'ordering': '-amount',
                'prison': [
                    prisons[0]['nomis_id'],
                ],
                'simple_search': 'Joh',
            },
        )

        self.assertDictEqual(
            form.get_query_data(),
            {
                'ordering': '-amount',
                'prison': [
                    prisons[0]['nomis_id'],
                ],
                'simple_search': 'Joh',
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
                {'prison': ['invalid']},
                {'prison': ['Select a valid choice. invalid is not one of the available choices.']},
            ),
        ]

        for scenario in scenarios:
            with responses.RequestsMock() as rsps:
                mock_prison_response(rsps)
                form = self.form_class(self.request, data=scenario.data)
            self.assertFalse(form.is_valid())
            self.assertDictEqual(form.errors, scenario.errors)
