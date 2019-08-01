from urllib.parse import parse_qs

import responses

from security.forms.prisoners import PrisonersForm, PrisonersFormV2
from security.tests.utils import mock_empty_response, mock_prison_response
from security.tests.forms.test_base import SecurityFormTestCase, ValidationScenario


class PrisonerFormTestCase(SecurityFormTestCase):
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
            self.assertDictEqual(
                parse_qs(rsps.calls[-1].request.url.split('?', 1)[1]),
                parse_qs('offset=0&limit=20&ordering=-sender_count'),
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 1,
                'ordering': '-sender_count',
                'prison': [],
                'simple_search': '',
            },
        )
        self.assertDictEqual(
            form.get_query_data(),
            {'ordering': '-sender_count'},
        )
        self.assertEqual(
            form.query_string,
            'ordering=-sender_count',
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
                    'ordering': '-credit_total',
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
                parse_qs('offset=20&limit=20&ordering=-credit_total&prison=IXB&simple_search=Joh'),
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 2,
                'ordering': '-credit_total',
                'prison': [
                    prisons[0]['nomis_id'],
                ],
                'simple_search': 'Joh',
            },
        )

        self.assertDictEqual(
            form.get_query_data(),
            {
                'ordering': '-credit_total',
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
