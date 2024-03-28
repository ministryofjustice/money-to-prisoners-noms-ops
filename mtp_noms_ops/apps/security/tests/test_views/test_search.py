import base64
import datetime
import contextlib
import json
import re
from unittest import mock
from urllib.parse import parse_qs

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from mtp_common.test_utils import silence_logger
from mtp_common.test_utils.notify import NotifyMock, GOVUK_NOTIFY_TEST_API_KEY
import responses

from security.forms.object_list import PrisonSelectorSearchFormMixin, PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE
from security.tests import api_url, mock_empty_response, TEST_IMAGE_DATA
from security.tests.test_views import SecurityBaseTestCase
from security.tests.test_views import SAMPLE_PRISONS, mock_prison_response, no_saved_searches
from security.views.object_base import SEARCH_FORM_SUBMITTED_INPUT_NAME


class AbstractSecurityViewTestCase(SecurityBaseTestCase):
    view_name = NotImplemented
    advanced_search_view_name = NotImplemented
    search_results_view_name = NotImplemented
    detail_view_name = NotImplemented
    search_ordering = NotImplemented
    api_list_path = NotImplemented

    # the filter name used for API calls, it's usually prison but can sometimes be current_prison
    prison_api_filter_name = 'prison'

    export_view_name = NotImplemented
    export_email_view_name = NotImplemented
    export_expected_xls_headers = NotImplemented
    export_expected_xls_rows = NotImplemented

    bank_transfer_sender = {
        'id': 9,
        'credit_count': 4,
        'credit_total': 41000,
        'prisoner_count': 3,
        'prison_count': 2,
        'prisons': [
            {
                'nomis_id': 'PRN',
                'name': 'Prison PRN',
            },
            {
                'nomis_id': 'ABC',
                'name': 'Prison ABC',
            },
        ],
        'bank_transfer_details': [
            {
                'sender_name': 'MAISIE NOLAN',
                'sender_sort_code': '101010',
                'sender_account_number': '12312345',
                'sender_roll_number': '',
            }
        ],
        'created': '2016-05-25T20:24:00Z',
        'modified': '2016-05-25T20:24:00Z',
    }
    debit_card_sender = {
        'id': 9,
        'credit_count': 4,
        'credit_total': 42000,
        'prisoner_count': 3,
        'prison_count': 2,
        'prisons': [
            {
                'nomis_id': 'PRN',
                'name': 'Prison PRN',
            },
            {
                'nomis_id': 'ABC',
                'name': 'Prison ABC',
            },
        ],
        'bank_transfer_details': [],
        'debit_card_details': [
            {
                'card_number_last_digits': '1234',
                'card_expiry_date': '10/20',
                'postcode': 'SW137NJ',
                'sender_emails': ['m@outside.local', 'M@OUTSIDE.LOCAL', 'mn@outside.local'],
                'cardholder_names': ['Maisie N', 'MAISIE N', 'Maisie Nolan'],
            }
        ],
        'created': '2016-05-25T20:24:00Z',
        'modified': '2016-05-25T20:24:00Z',
    }
    prisoner_profile = {
        'id': 8,
        'credit_count': 3,
        'credit_total': 31000,
        'sender_count': 2,
        'disbursement_count': 2,
        'disbursement_total': 29000,
        'recipient_count': 1,
        'prisoner_name': 'JAMES HALLS',
        'prisoner_number': 'A1409AE',
        'prisoner_dob': '1986-12-09',
        'current_prison': {'nomis_id': 'PRN', 'name': 'Prison PRN'},
        'prisons': [{'nomis_id': 'PRN', 'name': 'Prison PRN'}],
        'provided_names': ['Jim Halls', 'JAMES HALLS', 'James Halls '],
        'created': '2016-05-25T20:24:00Z',
        'modified': '2016-05-25T20:24:00Z',
    }
    credit_object = {
        'id': 1,
        'amount': 10250,
        'resolution': 'credited', 'anonymous': False,
        'credited_at': '2016-05-25T20:24:00Z',
        'owner': 1, 'owner_name': 'Clerk',
        'prison': 'PRN', 'prison_name': 'Prison', 'prisoner_name': 'JAMES HALLS', 'prisoner_number': 'A1409AE',
        'reconciliation_code': None,
        'received_at': '2017-01-25T12:00:00Z',
        'refunded_at': None,
        'reviewed': False, 'comments': [],
        'source': 'bank_transfer',
        'sender_sort_code': '101010', 'sender_account_number': '12312345', 'sender_roll_number': '',
        'card_expiry_date': None, 'card_number_last_digits': None,
        'sender_name': 'MAISIE NOLAN',
        'sender_email': None,
        'intended_recipient': None,
    }

    def get_api_object_list_response_data(self):
        """
        Return the list of objects that the mocked api should return in the tests.
        """
        return []

    @responses.activate
    @mock.patch('security.forms.object_base.SecurityForm.get_object_list')
    def test_can_access_security_view(self, mocked_form_method):
        mocked_form_method.return_value = []
        mock_prison_response()
        self.login(responses)
        response = self.client.get(reverse(self.view_name), follow=True)
        self.assertContains(response, '<!-- %s -->' % self.view_name)

    def test_displays_simple_search_results(self):
        """
        Test that the search results page includes the objects returned by the API
        in case of a simple search.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            api_results = self.get_api_object_list_response_data()
            rsps.add(
                rsps.GET,
                api_url(self.api_list_path),
                json={
                    'count': len(api_results),
                    'results': api_results,
                },
            )
            response = self.client.get(reverse(self.search_results_view_name))
        self._test_search_results_content(response, advanced=False)

    def test_displays_advanced_search_results(self):
        """
        Test that the search results page includes the objects returned by the API
        in case of an advanced search.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            api_results = self.get_api_object_list_response_data()
            rsps.add(
                rsps.GET,
                api_url(self.api_list_path),
                json={
                    'count': len(api_results),
                    'results': api_results,
                },
            )
            response = self.client.get(
                f'{reverse(self.search_results_view_name)}?advanced=True'
            )
        self._test_search_results_content(response, advanced=True)

    def _test_search_results_content(self, response, advanced=False):
        """
        Subclass to test that the response content of the search results view is as expected.
        """
        raise NotImplementedError

    def test_simple_search_uses_default_prisons(self):
        """
        Test that the simple search template uses the prisons of the logged in user to
        populate the `prison` hidden inputs.
        The simple search filters by the user's prisons by default.
        """
        with responses.RequestsMock() as rsps:
            user_data = self.get_user_data(prisons=SAMPLE_PRISONS)
            self.login(rsps, user_data=user_data)

            mock_prison_response(rsps=rsps)

            mock_empty_response(rsps, self.api_list_path)

            response = self.client.get(reverse(self.view_name))

        self.assertContains(
            response,
            f'<input type="hidden" name="prison_selector" value="{PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE}"',
        )

    def test_advanced_search_with_my_prisons_selection(self):
        """
        Test that if prison_selector == mine, the API call includes the prison filter with
        the expanted current user's prisons value.
        """
        with responses.RequestsMock() as rsps:
            user_prisons = SAMPLE_PRISONS[:1]
            user_data = self.get_user_data(prisons=user_prisons)
            self.login(rsps, user_data=user_data)

            mock_prison_response(rsps=rsps)

            mock_empty_response(rsps, self.api_list_path)

            url = (
                f'{reverse(self.advanced_search_view_name)}'
                f'?prison_selector={PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE}'
                f'&advanced=True&{SEARCH_FORM_SUBMITTED_INPUT_NAME}=1'
            )
            response = self.client.get(url, follow=True)
            self.assertEqual(response.status_code, 200)

            api_call_made = rsps.calls[-1].request.url
            parsed_qs = parse_qs(api_call_made.split('?', 1)[1])
            self.assertCountEqual(
                parsed_qs[self.prison_api_filter_name],
                [prison['nomis_id'] for prison in user_prisons],
            )

    def test_advanced_search_with_all_prisons_selection(self):
        """
        Test that if prison_selector == all, the API call doesn't include any prison filter.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)

            mock_prison_response(rsps=rsps)

            mock_empty_response(rsps, self.api_list_path)

            url = (
                f'{reverse(self.advanced_search_view_name)}'
                f'?prison_selector={PrisonSelectorSearchFormMixin.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE}'
                f'&advanced=True&{SEARCH_FORM_SUBMITTED_INPUT_NAME}=1'
            )
            response = self.client.get(url, follow=True)
            self.assertEqual(response.status_code, 200)

            api_call_made = rsps.calls[-1].request.url
            parsed_qs = parse_qs(api_call_made.split('?', 1)[1])
            self.assertTrue(self.prison_api_filter_name not in parsed_qs)

    def test_advanced_search_with_exact_prison_selected(self):
        """
        Test that if prison_selector == exact and a prison is specified, the API call
        includes exactly that prison filter.
        """
        with responses.RequestsMock() as rsps:
            expected_prison_id = SAMPLE_PRISONS[1]['nomis_id']

            self.login(rsps)

            mock_prison_response(rsps=rsps)

            mock_empty_response(rsps, self.api_list_path)

            url = (
                f'{reverse(self.advanced_search_view_name)}'
                f'?prison_selector={PrisonSelectorSearchFormMixin.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE}'
                f'&prison={expected_prison_id}'
                f'&advanced=True&{SEARCH_FORM_SUBMITTED_INPUT_NAME}=1'
            )
            response = self.client.get(url, follow=True)
            self.assertEqual(response.status_code, 200)

            api_call_made = rsps.calls[-1].request.url
            parsed_qs = parse_qs(api_call_made.split('?', 1)[1])
            self.assertCountEqual(
                parsed_qs[self.prison_api_filter_name],
                [expected_prison_id],
            )

    def test_simple_search_redirects_to_search_results_page(self):
        """
        Test that submitting the simple search form redirects to the results page when the form is valid.
        The action of submitting the form is represented by the query param
        SEARCH_FORM_SUBMITTED_INPUT_NAME which gets removed when redirecting.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)

            mock_prison_response(rsps=rsps)

            mock_empty_response(rsps, self.api_list_path)
            query_string = (
                f'prison_selector={PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE}'
                f'&advanced=False&ordering={self.search_ordering}&simple_search=test'
            )
            request_url = f'{reverse(self.view_name)}?{query_string}&{SEARCH_FORM_SUBMITTED_INPUT_NAME}=1'
            expected_redirect_url = f'{reverse(self.search_results_view_name)}?{query_string}'
            response = self.client.get(request_url)
            self.assertRedirects(
                response,
                expected_redirect_url,
            )

    def test_advanced_search_redirects_to_search_results_page(self):
        """
        Test that submitting the advanced search form redirects to the results page when the form is valid.
        The action of submitting the form is represented by the query param
        SEARCH_FORM_SUBMITTED_INPUT_NAME which gets removed when redirecting.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)

            mock_prison_response(rsps=rsps)

            mock_empty_response(rsps, self.api_list_path)

            query_string = (
                f'prison_selector={PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE}'
                f'&advanced=True&ordering={self.search_ordering}'
            )
            request_url = (
                f'{reverse(self.advanced_search_view_name)}?{query_string}&{SEARCH_FORM_SUBMITTED_INPUT_NAME}=1'
            )
            expected_redirect_url = f'{reverse(self.search_results_view_name)}?{query_string}'
            response = self.client.get(request_url)
            self.assertRedirects(
                response,
                expected_redirect_url,
            )

    def test_simple_search_doesnt_redirect_to_search_results_page_if_form_is_invalid(self):
        """
        Test that submitting the simple search form doesn't redirect to the results page when the form is invalid.
        The action of submitting the form is represented by the query param SEARCH_FORM_SUBMITTED_INPUT_NAME.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            query_string = 'ordering=invalid&simple_search=test'
            request_url = f'{reverse(self.view_name)}?{query_string}&{SEARCH_FORM_SUBMITTED_INPUT_NAME}=1'
            response = self.client.get(request_url)
            self.assertFalse(response.context['form'].is_valid())
            self.assertEqual(response.status_code, 200)

    def test_advanced_search_doesnt_redirect_to_search_results_page_if_form_is_invalid(self):
        """
        Test that submitting the advanced search form doesn't redirect to the results page when the form is invalid.
        The action of submitting the form is represented by the query param SEARCH_FORM_SUBMITTED_INPUT_NAME.
        """
        if not self.advanced_search_view_name:
            self.skipTest(f'Advanced search not yet implemented for {self.__class__.__name__}')

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            query_string = 'ordering=invalid&advanced=True'
            request_url = (
                f'{reverse(self.advanced_search_view_name)}?{query_string}&{SEARCH_FORM_SUBMITTED_INPUT_NAME}=1'
            )
            response = self.client.get(request_url)
            self.assertFalse(response.context['form'].is_valid())
            self.assertEqual(response.status_code, 200)

    def test_navigating_back_to_simple_search_form(self):
        """
        Test that going back to the simple search form doesn't redirect to the results page.
        The action of NOT submitting the form explicitly is represented by the absence of query param
        SEARCH_FORM_SUBMITTED_INPUT_NAME.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            mock_empty_response(rsps, self.api_list_path)
            query_string = f'ordering={self.search_ordering}&simple_search=test'
            request_url = f'{reverse(self.view_name)}?{query_string}'
            response = self.client.get(request_url)
            self.assertEqual(response.status_code, 200)

    def test_simple_search_results_with_link_to_all_prisons_search(self):
        """
        Test that if the current user's prisons value != 'all', after making a simple search,
        a link to search for the same thing in all prisons is shown.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            mock_empty_response(rsps, self.api_list_path)

            response = self.client.get(f'{reverse(self.search_results_view_name)}?simple_search=test')

        link_re = re.compile(
            (
                '<a href="(.*)'
                f'prison_selector={PrisonSelectorSearchFormMixin.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE}'
                '(.*)">'
                '(.*)See results from all prisons(.*)'
                '</a>'
            ),
            re.DOTALL,
        )
        self.assertTrue(
            link_re.search(response.content.decode('utf8')),
        )

    def test_simple_search_results_without_link_to_all_prisons_search(self):
        """
        Test that if the current user's prisons value == 'all', after making a simple search
        no link to search for the same thing in all prisons is shown as it would have the
        same result.
        """
        with responses.RequestsMock() as rsps:
            user_data = self.get_user_data(prisons=None)

            self.login(rsps, user_data=user_data)
            mock_prison_response(rsps=rsps)
            mock_empty_response(rsps, self.api_list_path)
            response = self.client.get(f'{reverse(self.search_results_view_name)}?simple_search=test')

        link_re = re.compile(
            (
                '<a href="(.*)'
                f'prison_selector={PrisonSelectorSearchFormMixin.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE}'
                '(.*)">'
                '(.*)See results from all prisons(.*)'
                '</a>'
            ),
            re.DOTALL,
        )
        self.assertFalse(
            link_re.search(response.content.decode('utf8')),
        )

    def test_displays_simple_search_results_with_all_prisons(self):
        """
        Test that when making a simple search with prison_selector == all,
        the API call doesn't include any prison filter.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            api_results = self.get_api_object_list_response_data()
            rsps.add(
                rsps.GET,
                api_url(self.api_list_path),
                json={
                    'count': len(api_results),
                    'results': api_results,
                },
            )
            url = (
                f'{reverse(self.search_results_view_name)}'
                '?simple_search=test'
                f'&prison_selector={PrisonSelectorSearchFormMixin.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE}'
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

            api_call_made = rsps.calls[-1].request.url
            parsed_qs = parse_qs(api_call_made.split('?', 1)[1])
            self.assertTrue(self.prison_api_filter_name not in parsed_qs)
            self.assertTrue('simple_search' in parsed_qs)

    def test_export_some_data(self):
        """
        Test that the export view generates a spreadsheet with only the content returned
        by the API.
        """
        expected_spreadsheet_content = [
            self.export_expected_xls_headers,
            *self.export_expected_xls_rows,
        ]

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(self.api_list_path),
                json={
                    'count': 2,
                    'results': self.get_api_object_list_response_data(),
                }
            )
            response = self.client.get(reverse(self.export_view_name))

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            response['Content-Type'],
        )
        self.assertSpreadsheetEqual(response.content, expected_spreadsheet_content)

    @override_settings(GOVUK_NOTIFY_API_KEY=GOVUK_NOTIFY_TEST_API_KEY)
    def test_email_export_some_data(self):
        """
        Test that the view sends the expected spreadsheet via email.
        """
        expected_spreadsheet_content = [
            self.export_expected_xls_headers,
            *self.export_expected_xls_rows,
        ]

        # get realistic referer
        qs = f'ordering={self.search_ordering}'
        response = self.client.get('/')
        referer_url = response.wsgi_request.build_absolute_uri(
            f'{reverse(self.view_name)}?{qs}',
        )

        with NotifyMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(self.api_list_path),
                json={
                    'count': 2,
                    'results': self.get_api_object_list_response_data(),
                }
            )
            response = self.client.get(
                f'{reverse(self.export_email_view_name)}?{qs}',
                HTTP_REFERER=referer_url,
            )
            self.assertRedirects(response, referer_url)
            self.assertEqual(len(mail.outbox), 0)
            attachment = base64.b64decode(rsps.send_email_request_data[0]['personalisation']['attachment']['file'])
            self.assertSpreadsheetEqual(
                attachment,
                expected_spreadsheet_content,
                msg='Emailed contents do not match expected',
            )

    def test_export_no_data(self):
        """
        Test that the export view generates a spreadsheet without rows if the API call doesn't return any record.
        """
        expected_spreadsheet_content = [
            self.export_expected_xls_headers,
        ]

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)

            mock_empty_response(rsps, self.api_list_path)

            response = self.client.get(reverse(self.export_view_name))

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            response['Content-Type'],
        )
        self.assertSpreadsheetEqual(response.content, expected_spreadsheet_content)

    @override_settings(GOVUK_NOTIFY_API_KEY=GOVUK_NOTIFY_TEST_API_KEY)
    def test_email_export_no_data(self):
        """
        Test that the view sends the an empty spreadsheet via email.
        """
        expected_spreadsheet_content = [
            self.export_expected_xls_headers,
        ]

        with NotifyMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)

            mock_empty_response(rsps, self.api_list_path)

            # get realistic referer
            qs = f'ordering={self.search_ordering}'
            response = self.client.get('/')
            referer_url = response.wsgi_request.build_absolute_uri(
                f'{reverse(self.view_name)}?{qs}',
            )

            response = self.client.get(
                f'{reverse(self.export_email_view_name)}?{qs}',
                HTTP_REFERER=referer_url,
            )
            self.assertRedirects(response, referer_url)
            self.assertEqual(len(mail.outbox), 0)
            attachment = base64.b64decode(rsps.send_email_request_data[0]['personalisation']['attachment']['file'])
            self.assertSpreadsheetEqual(
                attachment,
                expected_spreadsheet_content,
                msg='Emailed contents do not match expected',
            )

    def test_invalid_export_redirects_to_form(self):
        """
        Test that in case of invalid form, the export view redirects to the list page without
        taking any action.
        """
        # get realistic referer
        qs = 'ordering=invalid'
        response = self.client.get('/')
        referer_url = response.wsgi_request.build_absolute_uri(
            f'{reverse(self.view_name)}?{qs}',
        )

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            response = self.client.get(
                f'{reverse(self.export_view_name)}?{qs}',
                HTTP_REFERER=referer_url,
            )
            self.assertRedirects(response, referer_url)

    def test_invalid_email_export_redirects_to_form(self):
        """
        Test that in case of invalid form, the email export view redirects to the list page without
        taking any action.
        """
        # get realistic referer
        qs = 'ordering=invalid'
        response = self.client.get('/')
        referer_url = response.wsgi_request.build_absolute_uri(
            f'{reverse(self.view_name)}?{qs}',
        )

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            response = self.client.get(
                f'{reverse(self.export_email_view_name)}?{qs}',
                HTTP_REFERER=referer_url,
            )
            self.assertRedirects(response, referer_url)


class SenderViewsTestCase(AbstractSecurityViewTestCase):
    """
    Test case related to sender search and detail views.
    """
    view_name = 'security:sender_list'
    advanced_search_view_name = 'security:sender_advanced_search'
    search_results_view_name = 'security:sender_search_results'
    detail_view_name = 'security:sender_detail'
    search_ordering = '-prisoner_count'
    api_list_path = '/senders/'

    export_view_name = 'security:sender_export'
    export_email_view_name = 'security:sender_email_export'
    export_expected_xls_headers = [
        'Sender name',
        'Payment method',
        'Credits sent',
        'Total amount sent',
        'Prisoners sent to',
        'Prisons sent to',
        'Bank transfer sort code',
        'Bank transfer account',
        'Bank transfer roll number',
        'Debit card number',
        'Debit card expiry',
        'Debit card postcode',
        'Other cardholder names',
        'Cardholder emails',
    ]
    export_expected_xls_rows = [
        [
            'MAISIE NOLAN',
            'Bank transfer',
            4,
            '£410.00',
            3,
            2,
            '10-10-10',
            '12312345',
            None,
            None,
            None,
            None,
            None,
            None,
        ],
        [
            'Maisie N',
            'Debit card',
            4,
            '£420.00',
            3,
            2,
            None,
            None,
            None,
            '************1234',
            '10/20',
            'SW137NJ',
            'Maisie Nolan',
            'm@outside.local, mn@outside.local',
        ]
    ]

    def get_api_object_list_response_data(self):
        return [
            self.bank_transfer_sender,
            self.debit_card_sender,
        ]

    def _test_search_results_content(self, response, advanced=False):
        response_content = response.content.decode(response.charset)

        self.assertIn('2 payment sources', response_content)
        self.assertIn('MAISIE NOLAN', response_content)
        self.assertIn('£410.00', response_content)
        self.assertIn('£420.00', response_content)

        if advanced:
            self.assertIn('Prison PRN', response_content)
            self.assertIn('Prison ABC', response_content)
        else:
            self.assertNotIn('Prison PRN', response_content)
            self.assertNotIn('Prison ABC', response_content)

    def test_detail_view_displays_bank_transfer_detail(self):
        sender_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/'),
                json=self.bank_transfer_sender,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/credits/'),
                json={
                    'count': 4,
                    'results': [self.credit_object] * 4,
                },
            )

            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'sender_id': sender_id},
                ),
            )
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('MAISIE', response_content)
        self.assertIn('12312345', response_content)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('£102.50', response_content)

    def test_detail_view_displays_debit_card_detail(self):
        sender_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/'),
                json=self.debit_card_sender,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/credits/'),
                json={
                    'count': 4,
                    'results': [self.credit_object] * 4,
                }
            )
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'sender_id': sender_id},
                ),
            )
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('************1234', response_content)
        self.assertIn('10/20', response_content)
        self.assertIn('SW13 7NJ', response_content)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('£102.50', response_content)

    def test_detail_not_found(self):
        sender_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/'),
                status=404,
            )
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'sender_id': sender_id},
                    ),
                )
        self.assertEqual(response.status_code, 404)

    def test_connection_errors(self):
        sender_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(self.api_list_path),
                status=500,
            )
            with silence_logger('django.request'):
                response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'non-field-error')

        with responses.RequestsMock() as rsps:
            no_saved_searches(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/'),
                status=500,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/credits/'),
                status=500,
            )
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'sender_id': sender_id},
                    ),
                )
        self.assertContains(response, 'non-field-error')


class PrisonerViewsTestCase(AbstractSecurityViewTestCase):
    """
    Test case related to prisoner search and detail views.
    """
    view_name = 'security:prisoner_list'
    advanced_search_view_name = 'security:prisoner_advanced_search'
    search_results_view_name = 'security:prisoner_search_results'
    detail_view_name = 'security:prisoner_detail'
    search_ordering = '-sender_count'
    api_list_path = '/prisoners/'
    prison_api_filter_name = 'current_prison'

    export_view_name = 'security:prisoner_export'
    export_email_view_name = 'security:prisoner_email_export'
    export_expected_xls_headers = [
        'Prisoner number',
        'Prisoner name',
        'Date of birth',
        'Credits received',
        'Total amount received',
        'Payment sources',
        'Disbursements sent',
        'Total amount sent',
        'Recipients',
        'Current prison',
        'All known prisons',
        'Names given by senders',
    ]
    export_expected_xls_rows = [
        [
            'A1409AE',
            'JAMES HALLS',
            '1986-12-09',
            3,
            '£310.00',
            2,
            2,
            '£290.00',
            1,
            'Prison PRN',
            'Prison PRN',
            'Jim Halls, JAMES HALLS',
        ],
    ]
    expected_total_amount = '310.00'  # A1409AE credits total

    def get_api_object_list_response_data(self):
        return [self.prisoner_profile]

    def _test_search_results_content(self, response, advanced=False):
        response_content = response.content.decode(response.charset)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('A1409AE', response_content)
        self.assertIn(self.expected_total_amount, response_content)

        if advanced:
            self.assertIn('Prison PRN', response_content)
        else:
            self.assertNotIn('Prison PRN', response_content)

    @classmethod
    @contextlib.contextmanager
    def disbursements_view(cls):
        with (
            mock.patch.object(cls, 'search_results_view_name', 'security:prisoner_disbursement_search_results'),
            mock.patch.object(cls, 'expected_total_amount', '290.00'),
        ):
            yield

    def test_displays_simple_search_results_with_disbursements(self):
        with self.disbursements_view():
            self.test_displays_simple_search_results()

    def test_displays_advanced_search_results_with_disbursements(self):
        with self.disbursements_view():
            self.test_displays_advanced_search_results()

    def test_detail_view(self):
        prisoner_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/'),
                json=self.prisoner_profile,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/credits/'),
                json={
                    'count': 4,
                    'results': [self.credit_object] * 4,
                },
            )

            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'prisoner_id': prisoner_id},
                ),
            )
        response_content = response.content.decode(response.charset)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('Jim Halls', response_content)
        self.assertNotIn('James Halls', response_content)
        self.assertIn('MAISIE', response_content)
        self.assertIn('£102.50', response_content)

    def test_detail_not_found(self):
        prisoner_id = 999
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/'),
                status=404,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/credits/'),
                status=404,
            )
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'prisoner_id': prisoner_id},
                    ),
                )
        self.assertEqual(response.status_code, 404)

    def test_connection_errors(self):
        prisoner_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(self.api_list_path),
                status=500,
            )
            with silence_logger('django.request'):
                response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'non-field-error')

        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/'),
                status=500,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/credits/'),
                status=500,
            )
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'prisoner_id': prisoner_id},
                    ),
                )
        self.assertContains(response, 'non-field-error')

    def _add_prisoner_data_responses(self):
        responses.add(
            responses.GET,
            api_url('/prisoners/1/'),
            json=self.prisoner_profile,
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/1/credits/'),
            json={
                'count': 4,
                'results': [self.credit_object] * 4,
            },
        )

    @responses.activate
    @mock.patch('security.views.nomis.can_access_nomis', mock.Mock(return_value=True))
    @mock.patch('security.views.nomis.get_photograph_data', mock.Mock(return_value=TEST_IMAGE_DATA))
    def test_display_nomis_photo(self):
        self.login(responses, follow=False)
        response = self.client.get(
            reverse(
                'security:prisoner_image',
                kwargs={'prisoner_number': self.prisoner_profile['prisoner_number']}
            )
        )
        self.assertContains(response, base64.b64decode(TEST_IMAGE_DATA))

    @responses.activate
    @mock.patch('security.views.nomis.can_access_nomis', mock.Mock(return_value=True))
    @mock.patch('security.views.nomis.get_photograph_data', mock.Mock(return_value=None))
    def test_missing_nomis_photo(self):
        self.login(responses, follow=False)
        response = self.client.get(
            reverse(
                'security:prisoner_image',
                kwargs={'prisoner_number': self.prisoner_profile['prisoner_number']}
            ),
            follow=False
        )
        self.assertRedirects(response, '/static/images/placeholder-image.png', fetch_redirect_response=False)

    @responses.activate
    def test_display_pinned_profile(self):
        self._add_prisoner_data_responses()
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 1,
                'results': [
                    {
                        'id': 1,
                        'description': 'Saved search 1',
                        'endpoint': '/prisoners/1/credits/',
                        'last_result_count': 2,
                        'site_url': '/en-gb/security/prisoners/1/?ordering=-received_at',
                        'filters': []
                    },
                ]
            },
        )
        responses.add(
            responses.PATCH,
            api_url('/searches/1/'),
            status=204,
        )
        self.login(responses, follow=False)
        response = self.client.get(
            reverse(self.detail_view_name, kwargs={'prisoner_id': 1})
        )
        self.assertContains(response, 'Stop monitoring this prisoner')
        for call in responses.calls:
            if call.request.path_url == '/searches/1/':
                self.assertEqual(call.request.body, b'{"last_result_count": 4}')

    @responses.activate
    def test_pin_profile(self):
        self._add_prisoner_data_responses()
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 0,
                'results': []
            },
        )
        responses.add(
            responses.POST,
            api_url('/searches/'),
            status=201,
        )
        responses.add(
            responses.POST,
            api_url('/prisoners/1/monitor'),
            status=204,
        )

        self.login(responses, follow=False)
        self.client.get(
            reverse(self.detail_view_name, kwargs={'prisoner_id': 1}) +
            '?pin=1'
        )

        for call in responses.calls:
            if call.request.path_url == '/searches/':
                self.assertEqual(
                    json.loads(call.request.body.decode()),
                    {
                        'description': 'A1409AE JAMES HALLS',
                        'endpoint': '/prisoners/1/credits/',
                        'last_result_count': 4,
                        'site_url': '/en-gb/security/prisoners/1/',
                        'filters': [{'field': 'ordering', 'value': '-received_at'}],
                    },
                )


class CreditViewsTestCase(AbstractSecurityViewTestCase):
    """
    Test case related to credit search and detail views.
    """
    view_name = 'security:credit_list'
    advanced_search_view_name = 'security:credit_advanced_search'
    search_results_view_name = 'security:credit_search_results'
    detail_view_name = 'security:credit_detail'
    search_ordering = '-received_at'
    api_list_path = '/credits/'

    export_view_name = 'security:credit_export'
    export_email_view_name = 'security:credit_email_export'
    export_expected_xls_headers = [
        'Internal ID',
        'Date started', 'Date received', 'Date credited',
        'Amount',
        'Prisoner number', 'Prisoner name', 'Prison',
        'Sender name', 'Payment method',
        'Bank transfer sort code', 'Bank transfer account', 'Bank transfer roll number',
        'Debit card number', 'Debit card expiry', 'Debit card billing address',
        'Sender email', 'Sender IP address',
        'Status',
        'NOMIS transaction',
    ]
    export_expected_xls_rows = [
        [
            1,
            '2016-05-25 21:21:00',  # in Europe/London
            '2016-05-25 21:24:00',
            '2016-05-26 09:27:00',
            '£230.00',
            'A1411AE',
            'GEORGE MELLEY',
            'HMP LEEDS',
            None,
            'Debit card',
            None,
            None,
            None,
            '111122******4444',
            '07/18',
            '102PF, London',
            'ian@mail.local',
            '127.0.0.1',
            'Credited',
            None,
        ],
        [
            2,
            None,
            '2016-05-22',
            '2016-05-23 09:10:00',
            '£275.00',
            'A1413AE',
            'NORMAN STANLEY FLETCHER',
            'HMP LEEDS',
            'HEIDENREICH X',
            'Bank transfer',
            '21-96-57',
            '88447894',
            None,
            None,
            None,
            None,
            None,
            None,
            'Credited',
            '123456-7',
        ],
    ]

    debit_card_credit = {
        'id': 1,
        'source': 'online',
        'amount': 23000,
        'intended_recipient': 'Mr G Melley',
        'prisoner_number': 'A1411AE',
        'prisoner_name': 'GEORGE MELLEY',
        'prison': 'LEI',
        'prison_name': 'HMP LEEDS',
        'sender_name': None,
        'sender_sort_code': None,
        'sender_account_number': None,
        'sender_email': 'ian@mail.local',
        'billing_address': {'line1': '102PF', 'city': 'London'},
        'sender_roll_number': None,
        'card_number_first_digits': '111122',
        'card_number_last_digits': '4444',
        'card_expiry_date': '07/18',
        'resolution': 'credited',
        'owner': None,
        'owner_name': 'Maria',
        'started_at': '2016-05-25T20:21:00Z',
        'received_at': '2016-05-25T20:24:00Z',
        'credited_at': '2016-05-26T08:27:00Z',
        'refunded_at': None,
        'comments': [{'user_full_name': 'Eve', 'comment': 'OK'}],
        'nomis_transaction_id': None,
        'ip_address': '127.0.0.1',
    }
    bank_transfer_credit = {
        'id': 2,
        'source': 'bank_transfer',
        'amount': 27500,
        'intended_recipient': None,
        'prisoner_number': 'A1413AE',
        'prisoner_name': 'NORMAN STANLEY FLETCHER',
        'prison': 'LEI',
        'prison_name': 'HMP LEEDS',
        'sender_name': 'HEIDENREICH X',
        'sender_email': None,
        'billing_address': None,
        'sender_sort_code': '219657',
        'sender_account_number': '88447894',
        'card_number_last_digits': None,
        'card_expiry_date': None,
        'sender_roll_number': '',
        'resolution': 'credited',
        'owner': None,
        'owner_name': 'Maria',
        'started_at': None,
        'received_at': '2016-05-22T12:00:00Z',
        'credited_at': '2016-05-23T08:10:00Z',
        'refunded_at': None,
        'comments': [],
        'nomis_transaction_id': '123456-7',
        'ip_address': None,
    }

    def get_api_object_list_response_data(self):
        return [
            self.debit_card_credit,
            self.bank_transfer_credit,
        ]

    def _test_search_results_content(self, response, advanced=False):
        response_content = response.content.decode(response.charset)
        self.assertIn('2 credits', response_content)

        self.assertIn('GEORGE MELLEY', response_content)
        self.assertIn('A1411AE', response_content)
        self.assertIn('230.00', response_content)

        self.assertIn('NORMAN STANLEY FLETCHER', response_content)
        self.assertIn('A1413AE', response_content)
        self.assertIn('275.00', response_content)

        # results page via advanced search includes an extra `prison` column
        if advanced:
            self.assertIn('HMP LEEDS', response_content)
        else:
            self.assertNotIn('HMP LEEDS', response_content)

    def test_detail_view_displays_debit_card_detail(self):
        credit_id = 2
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                f'{api_url(self.api_list_path)}?pk={credit_id}',
                json={
                    'count': 1,
                    'previous': None,
                    'next': None,
                    'results': [self.debit_card_credit],
                }
            )

            self.login(rsps)
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'credit_id': credit_id},
                ),
            )
        self.assertContains(response, 'Debit card')
        response_content = response.content.decode(response.charset)
        self.assertIn('£230.00', response_content)
        self.assertIn('GEORGE MELLEY', response_content)
        self.assertIn('Mr G Melley', response_content)
        self.assertIn('A1411AE', response_content)
        self.assertIn('Maria credited to NOMIS', response_content)
        self.assertIn('Eve', response_content)
        self.assertIn('OK', response_content)

    def test_detail_view_displays_bank_transfer_detail(self):
        credit_id = 2
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                f'{api_url(self.api_list_path)}?pk={credit_id}',
                json={
                    'count': 1,
                    'previous': None,
                    'next': None,
                    'results': [self.bank_transfer_credit],
                }
            )

            self.login(rsps)
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'credit_id': credit_id},
                ),
            )
        self.assertContains(response, 'Bank transfer')
        response_content = response.content.decode(response.charset)
        self.assertIn('£275.00', response_content)
        self.assertIn('NORMAN STANLEY FLETCHER', response_content)
        self.assertIn('21-96-57', response_content)
        self.assertIn('88447894', response_content)
        self.assertIn('Maria credited to NOMIS', response_content)

    def test_detail_not_found(self):
        credit_id = 999
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                f'{api_url(self.api_list_path)}?pk={credit_id}',
                json={
                    'count': 0,
                    'previous': None,
                    'next': None,
                    'results': [],
                }
            )

            self.login(rsps)
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'credit_id': credit_id},
                    ),
                )
        self.assertEqual(response.status_code, 404)

    @mock.patch('security.views.object_base.email_export_xlsx')
    def test_email_export_uses_api_params(self, mocked_email_export_xlsx):
        """
        Calls to the mtp-api must adjust parameters (see form.get_api_request_params)
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)

            # get realistic referer
            qs = f'ordering={self.search_ordering}&advanced=True&' \
                 'received_at__lt_0=8&received_at__lt_1=7&received_at__lt_2=2022'
            response = self.client.get('/')
            referer_url = response.wsgi_request.build_absolute_uri(
                f'{reverse(self.view_name)}?{qs}',
            )

            self.client.get(
                f'{reverse(self.export_email_view_name)}?{qs}',
                HTTP_REFERER=referer_url,
            )
            mocked_email_export_xlsx.assert_called_once()
            api_filters = mocked_email_export_xlsx.call_args.kwargs['filters']
            # expect valid param to pass through
            self.assertEqual(api_filters['ordering'], self.search_ordering)
            # SearchFormMixin removes this param
            self.assertNotIn('advanced', api_filters)
            # exclusive_date_params are incremented
            # because the form presents an inclusive date range: [received_at__gte, received_at__lt]
            # but the api needs an exclusive range: [received_at__gte, received_at__lt)
            self.assertEqual(api_filters['received_at__lt'], datetime.date(2022, 7, 9))


class DisbursementViewsTestCase(AbstractSecurityViewTestCase):
    """
    Test case related to disbursement search and detail views.
    """
    view_name = 'security:disbursement_list'
    advanced_search_view_name = 'security:disbursement_advanced_search'
    search_results_view_name = 'security:disbursement_search_results'
    detail_view_name = 'security:disbursement_detail'
    search_ordering = '-created'
    api_list_path = '/disbursements/'

    export_view_name = 'security:disbursement_export'
    export_email_view_name = 'security:disbursement_email_export'
    export_expected_xls_headers = [
        'Internal ID',
        'Date entered', 'Date confirmed', 'Date sent',
        'Amount',
        'Prisoner number', 'Prisoner name', 'Prison',
        'Recipient name', 'Payment method',
        'Bank transfer sort code', 'Bank transfer account', 'Bank transfer roll number',
        'Recipient address', 'Recipient email',
        'Status',
        'NOMIS transaction', 'SOP invoice number',
    ]
    export_expected_xls_rows = [
        [
            99,
            '2018-02-12 12:00:00',
            '2018-02-12 11:00:00',
            '2018-02-12 12:00:00',
            '£20.00',
            'A1409AE',
            'JAMES HALLS',
            'HMP Test1',
            'Jack Halls',
            'Bank transfer',
            '11-22-33',
            '1234567',
            None,
            '102 Petty France, London, SW1H 9AJ',
            None,
            'Sent',
            '1234567-1',
            '1000099',
        ],
        [
            100,
            '2018-02-10 10:00:00',
            '2018-02-10 02:00:00',
            None,
            '£10.00',
            'A1401AE',
            'JILLY HALL',
            'HMP Test2',
            'Jilly Halls',
            'Cheque',
            None,
            None,
            None,
            '102 Petty France, London, SW1H 9AJ',
            'jilly@mtp.local',
            'Confirmed',
            '1234568-1',
            None,
        ],
    ]

    bank_transfer_disbursement = {
        'id': 99,
        'created': '2018-02-12T12:00:00Z',
        'modified': '2018-02-12T12:00:00Z',
        'method': 'bank_transfer',
        'amount': 2000,
        'resolution': 'sent',
        'nomis_transaction_id': '1234567-1',
        'invoice_number': '1000099',
        'prisoner_number': 'A1409AE',
        'prisoner_name': 'JAMES HALLS',
        'prison': 'ABC',
        'prison_name': 'HMP Test1',
        'recipient_first_name': 'Jack',
        'recipient_last_name': 'Halls',
        'recipient_email': '',
        'remittance_description': '',
        'address_line1': '102 Petty France',
        'address_line2': '',
        'city': 'London',
        'postcode': 'SW1H 9AJ',
        'country': None,
        'account_number': '1234567',
        'sort_code': '112233',
        'roll_number': None,
        'comments': [],
        'log_set': [
            {
                'action': 'created',
                'created': '2018-02-12T10:00:00Z',
                'user': {'first_name': 'Mary', 'last_name': 'Smith', 'username': 'msmith'}
            },
            {
                'action': 'confirmed',
                'created': '2018-02-12T11:00:00Z',
                'user': {'first_name': 'John', 'last_name': 'Smith', 'username': 'jsmith'}
            },
            {
                'action': 'sent',
                'created': '2018-02-12T12:00:00Z',
                'user': {'first_name': 'SSCL', 'last_name': '', 'username': 'sscl'}
            }
        ],
    }
    cheque_disbursement = {
        'id': 100,
        'created': '2018-02-10T10:00:00Z',
        'modified': '2018-02-10T12:00:00Z',
        'method': 'cheque',
        'amount': 1000,
        'resolution': 'confirmed',
        'nomis_transaction_id': '1234568-1',
        'invoice_number': None,
        'prisoner_number': 'A1401AE',
        'prisoner_name': 'JILLY HALL',
        'prison': 'DEF',
        'prison_name': 'HMP Test2',
        'recipient_first_name': 'Jilly',
        'recipient_last_name': 'Halls',
        'recipient_email': 'jilly@mtp.local',
        'remittance_description': 'PRESENT',
        'address_line1': '102 Petty France',
        'address_line2': '',
        'city': 'London',
        'postcode': 'SW1H 9AJ',
        'country': None,
        'account_number': '',
        'sort_code': '',
        'roll_number': None,
        'comments': [],
        'log_set': [
            {
                'action': 'created',
                'created': '2018-02-10T01:00:00Z',
                'user': {'first_name': 'Mary', 'last_name': 'Smith', 'username': 'msmith'}
            },
            {
                'action': 'confirmed',
                'created': '2018-02-10T02:00:00Z',
                'user': {'first_name': 'John', 'last_name': 'Smith', 'username': 'jsmith'}
            }
        ],
    }

    def get_api_object_list_response_data(self):
        return [
            self.bank_transfer_disbursement,
            self.cheque_disbursement,
        ]

    def _test_search_results_content(self, response, advanced=False):
        response_content = response.content.decode(response.charset)
        self.assertIn('2 disbursements', response_content)

        self.assertIn('Jack Halls', response_content)
        self.assertIn('20.00', response_content)
        self.assertIn('A1409AE', response_content)

        self.assertIn('Jilly Halls', response_content)
        self.assertIn('10.00', response_content)
        self.assertIn('A1401AE', response_content)

        # results page via advanced search includes an extra `prison` column
        if advanced:
            self.assertIn('HMP Test1', response_content)
            self.assertIn('HMP Test2', response_content)
        else:
            self.assertNotIn('HMP Test1', response_content)
            self.assertNotIn('HMP Test2', response_content)

    def test_detail_view_displays_bank_transfer_detail(self):
        disbursement_id = 99
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/disbursements/{disbursement_id}/'),
                json=self.bank_transfer_disbursement,
            )

            self.login(rsps)
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'disbursement_id': disbursement_id},
                ),
            )
        self.assertContains(response, 'Bank transfer')
        self.assertContains(response, '20.00')
        self.assertContains(response, 'JAMES HALLS')
        self.assertContains(response, 'Jack Halls')
        self.assertContains(response, '1234567-1')
        self.assertContains(response, '1000099')
        self.assertContains(response, 'Confirmed by John Smith')
        self.assertContains(response, 'None given')

    def test_detail_view_displays_cheque_detail(self):
        disbursement_id = 100
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/disbursements/{disbursement_id}/'),
                json=self.cheque_disbursement,
            )

            self.login(rsps)
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'disbursement_id': disbursement_id},
                ),
            )
        self.assertContains(response, 'Cheque')
        self.assertContains(response, '10.00')
        self.assertContains(response, 'JILLY HALL')
        self.assertContains(response, 'Jilly Halls')
        self.assertContains(response, '1234568-1')
        self.assertContains(response, 'Confirmed by John Smith')
        self.assertContains(response, 'jilly@mtp.local')
        self.assertContains(response, 'PRESENT')

    def test_detail_not_found(self):
        disbursement_id = 999
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/disbursements/{disbursement_id}/'),
                status=404,
            )

            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'disbursement_id': disbursement_id},
                    ),
                )
        self.assertEqual(response.status_code, 404)

    @mock.patch('security.views.object_base.email_export_xlsx')
    def test_email_export_uses_api_params(self, mocked_email_export_xlsx):
        """
        Calls to the mtp-api must adjust parameters (see form.get_api_request_params)
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            mock_prison_response(rsps=rsps)

            # get realistic referer
            qs = f'ordering={self.search_ordering}&advanced=True&' \
                 'created__lt_0=8&created__lt_1=7&created__lt_2=2022'
            response = self.client.get('/')
            referer_url = response.wsgi_request.build_absolute_uri(
                f'{reverse(self.view_name)}?{qs}',
            )

            self.client.get(
                f'{reverse(self.export_email_view_name)}?{qs}',
                HTTP_REFERER=referer_url,
            )
            mocked_email_export_xlsx.assert_called_once()
            api_filters = mocked_email_export_xlsx.call_args.kwargs['filters']
            # expect valid param to pass through
            self.assertEqual(api_filters['ordering'], self.search_ordering)
            # SearchFormMixin removes this param
            self.assertNotIn('advanced', api_filters)
            # exclusive_date_params are incremented
            # because the form presents an inclusive date range: [created__gte, created__lt]
            # but the api needs an exclusive range: [created__gte, created__lt)
            self.assertEqual(api_filters['created__lt'], datetime.date(2022, 7, 9))


del AbstractSecurityViewTestCase
