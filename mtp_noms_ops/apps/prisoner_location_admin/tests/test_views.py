from unittest import mock

from django.core.urlresolvers import reverse
from django.test import SimpleTestCase
from mtp_common.auth.test_utils import generate_tokens
from slumber.exceptions import HttpClientError

from . import generate_testable_location_data, get_csv_data_as_file
from prisoner_location_admin import required_permissions


class PrisonerLocationAdminViewsTestCase(SimpleTestCase):
    @mock.patch('mtp_common.auth.backends.api_client')
    def login(self, mock_api_client):
        mock_api_client.authenticate.return_value = {
            'pk': 5,
            'token': generate_tokens(),
            'user_data': {
                'first_name': 'Sam',
                'last_name': 'Hall',
                'username': 'shall',
                'permissions': required_permissions,
            }
        }

        response = self.client.post(
            reverse('login'),
            data={'username': 'shall', 'password': 'pass'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        return response

    def check_login_redirect(self, attempted_url):
        response = self.client.get(attempted_url)
        redirect_url = '%(login_url)s?next=%(attempted_url)s' % {
            'login_url': reverse('login'),
            'attempted_url': attempted_url
        }
        self.assertRedirects(response, redirect_url)

    def test_requires_login_upload(self):
        self.check_login_redirect(reverse('location_file_upload'))

    def test_can_access_prisoner_location_admin(self):
        response = self.login()
        self.assertContains(response, '<!-- location_file_upload -->')

    def test_cannot_access_security_dashboard(self):
        self.login()
        response = self.client.get(reverse('security_dashboard'), follow=True)
        self.assertNotContains(response, '<!-- security_dashboard -->')
        self.assertContains(response, '<!-- location_file_upload -->')

    @mock.patch('prisoner_location_admin.forms.api_client')
    def test_location_file_upload(self, mock_api_client):
        self.login()

        conn = mock_api_client.get_connection().prisoner_locations
        conn.post.return_value = 200

        file_data, expected_data = generate_testable_location_data()

        response = self.client.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file(file_data)}
        )

        conn.post.assert_called_with(expected_data)
        self.assertRedirects(response, reverse('location_file_upload'))

    @mock.patch('prisoner_location_admin.forms.api_client')
    def test_location_file_upload_api_error_displays_message(self, mock_api_client):
        self.login()

        api_error_message = 'Bad Request'

        conn = mock_api_client.get_connection().prisoner_locations
        conn.post.side_effect = HttpClientError(content=api_error_message)

        file_data, _ = generate_testable_location_data()

        response = self.client.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file(file_data)}
        )

        self.assertContains(response, api_error_message)
