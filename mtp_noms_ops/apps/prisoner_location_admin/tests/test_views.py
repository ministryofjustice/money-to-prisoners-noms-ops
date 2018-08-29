import json
import logging
from unittest import mock

from django.core.urlresolvers import reverse
from mtp_common.auth.exceptions import Forbidden
from mtp_common.test_utils import silence_logger
import responses

from security.tests import api_url
from . import (
    PrisonerLocationUploadTestCase, generate_testable_location_data,
    get_csv_data_as_file
)


class PrisonerLocationAdminViewsTestCase(PrisonerLocationUploadTestCase):

    def check_login_redirect(self, attempted_url):
        response = self.client.get(attempted_url)
        redirect_url = '%(login_url)s?next=%(attempted_url)s' % {
            'login_url': reverse('login'),
            'attempted_url': attempted_url
        }
        self.assertRedirects(response, redirect_url)

    @mock.patch('mtp_common.auth.backends.api_client')
    def test_cannot_login_with_incorrect_details(self, mock_api_client):
        mock_api_client.authenticate.return_value = None

        response = self.client.post(
            reverse('login'),
            data={'username': 'shall', 'password': 'pass'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())

    @mock.patch('mtp_common.auth.backends.api_client')
    def test_cannot_login_without_app_access(self, mock_api_client):
        mock_api_client.authenticate.side_effect = Forbidden

        response = self.client.post(
            reverse('login'),
            data={'username': 'shall', 'password': 'pass'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())

    def test_requires_login_upload(self):
        self.check_login_redirect(reverse('location_file_upload'))

    def test_can_access_prisoner_location_admin(self):
        self.login()
        response = self.client.get(reverse('location_file_upload'))
        self.assertContains(response, '<!-- location_file_upload -->')

    def test_cannot_access_security_views(self):
        self.login()
        response = self.client.get(reverse('security:credit_list'), follow=True)
        self.assertNotContains(response, '<!-- security:credit_list -->')
        self.assertContains(response, '<!-- location_file_upload -->')

    @responses.activate
    @mock.patch('prisoner_location_admin.tasks.api_client')
    def test_location_file_upload(self, mock_api_client):
        self.login()
        self.setup_mock_get_authenticated_api_session(mock_api_client)

        responses.add(
            responses.POST,
            api_url('/prisoner_locations/actions/delete_inactive/')
        )
        responses.add(
            responses.POST,
            api_url('/prisoner_locations/')
        )
        responses.add(
            responses.POST,
            api_url('/prisoner_locations/actions/delete_old/')
        )

        file_data, expected_data = generate_testable_location_data()

        with silence_logger(level=logging.WARNING):
            response = self.client.post(
                reverse('location_file_upload'),
                {'location_file': get_csv_data_as_file(file_data)}
            )

        expected_calls = [expected_data]

        for call in responses.calls:
            if call.request.url == api_url('/prisoner_locations/'):
                self.assertEqual(
                    json.loads(call.request.body.decode()),
                    expected_calls.pop()
                )

        if expected_calls:
            self.fail('Not all location data was uploaded')

        self.assertRedirects(response, reverse('location_file_upload'))

    @responses.activate
    @mock.patch('prisoner_location_admin.tasks.api_client')
    def test_location_file_upload_api_error_displays_message(self, mock_api_client):
        self.login()
        self.setup_mock_get_authenticated_api_session(mock_api_client)

        api_error_message = 'prison not found'
        response_content = ('[{"prison": ["%s"]}]' % api_error_message).encode()

        responses.add(
            responses.POST,
            api_url('/prisoner_locations/actions/delete_inactive/')
        )
        responses.add(
            responses.POST,
            api_url('/prisoner_locations/'),
            status=400,
            body=response_content
        )

        file_data, _ = generate_testable_location_data()

        with silence_logger():
            response = self.client.post(
                reverse('location_file_upload'),
                {'location_file': get_csv_data_as_file(file_data)}
            )

        self.assertContains(response, api_error_message)
