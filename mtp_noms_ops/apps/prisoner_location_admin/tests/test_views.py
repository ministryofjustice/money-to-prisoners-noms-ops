import logging
from unittest import mock

from django.core.urlresolvers import reverse
from mtp_common.auth.exceptions import Forbidden
from slumber.exceptions import HttpClientError

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

    def test_cannot_access_security_dashboard(self):
        self.login()
        response = self.client.get(reverse('security:dashboard'), follow=True)
        self.assertNotContains(response, '<!-- security:dashboard -->')
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

        api_error_message = "prison not found"
        response_content = ('[{"prison": ["%s"]}]' % api_error_message).encode('utf-8')

        conn = mock_api_client.get_connection().prisoner_locations
        conn.post.side_effect = HttpClientError(content=response_content)

        file_data, _ = generate_testable_location_data()

        logger = logging.getLogger('mtp')
        previous_logging_level = logger.level
        logger.setLevel(logging.CRITICAL)
        response = self.client.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file(file_data)}
        )
        logger.setLevel(previous_logging_level)

        self.assertContains(response, api_error_message)
