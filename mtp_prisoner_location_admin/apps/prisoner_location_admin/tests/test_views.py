from unittest import mock

from django.test import SimpleTestCase
from django.core.urlresolvers import reverse

from moj_auth.tests.utils import generate_tokens
from .data import VALID_FILE_PATH, EXPECTED_VALID_LOCATIONS


class PrisonerLocationAdminViewsTestCase(SimpleTestCase):

    @mock.patch('moj_auth.backends.api_client')
    def login(self, mock_api_client):
        mock_api_client.authenticate.return_value = {
            'pk': 5,
            'token': generate_tokens(),
            'user_data': {
                'first_name': 'Sam',
                'last_name': 'Hall',
                'username': 'shall'
            }
        }

        response = self.client.post(
            reverse('login'),
            data={'username': 'shall', 'password': 'pass'},
            follow=True
        )

        self.assertEqual(response.status_code, 200)

    def check_login_redirect(self, attempted_url):
        response = self.client.get(attempted_url)
        redirect_url = '%(login_url)s?next=%(attempted_url)s' % {
            'login_url': reverse('login'),
            'attempted_url': attempted_url
        }
        self.assertRedirects(response, redirect_url)

    def test_requires_login_dashboard(self):
        self.check_login_redirect(reverse('dashboard'))

    def test_requires_login_upload(self):
        self.check_login_redirect(reverse('location_file_upload'))

    @mock.patch('prisoner_location_admin.forms.api_client')
    def test_location_file_upload(self, mock_api_client):
        self.login()

        conn = mock_api_client.get_connection().prisoner_locations
        conn.post.return_value = 200

        with open(VALID_FILE_PATH) as f:
            response = self.client.post(reverse('location_file_upload'),
                                        {'location_file': f})

        conn.post.assert_called_with(EXPECTED_VALID_LOCATIONS)
        self.assertRedirects(response, reverse('dashboard'))
