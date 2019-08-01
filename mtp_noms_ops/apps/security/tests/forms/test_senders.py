from urllib.parse import parse_qs

import responses

from security.forms.senders import SendersForm, SendersFormV2
from security.tests.utils import mock_empty_response, mock_prison_response
from security.tests.forms.test_base import SecurityFormTestCase, ValidationScenario


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
            self.assertDictEqual(
                parse_qs(rsps.calls[-1].request.url.split('?', 1)[1]),
                parse_qs('offset=0&limit=20&ordering=-prisoner_count'),
            )

        self.assertDictEqual(
            form.cleaned_data,
            {
                'page': 1,
                'ordering': '-prisoner_count',
                'prison': [],
                'simple_search': '',
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
