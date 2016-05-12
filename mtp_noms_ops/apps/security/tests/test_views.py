from unittest import mock

from django.core.urlresolvers import reverse
from django.test import SimpleTestCase
from mtp_common.auth.test_utils import generate_tokens

from security import required_permissions


class SecurityDashboardViewsTestCase(SimpleTestCase):
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

    def test_can_access_security_dashboard(self):
        response = self.login()
        self.assertContains(response, '<!-- security_dashboard -->')

    def test_cannot_access_prisoner_location_admin(self):
        self.login()
        response = self.client.get(reverse('location_file_upload'), follow=True)
        self.assertNotContains(response, '<!-- location_file_upload -->')
        self.assertContains(response, '<!-- security_dashboard -->')
