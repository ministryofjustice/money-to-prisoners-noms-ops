from django.urls import reverse
from mtp_common.test_utils import silence_logger
import responses
from responses.matchers import json_params_matcher

from security import required_permissions
from security.tests import api_url, mock_empty_response
from security.tests.test_views.test_checks import BaseCheckViewTestCase


class MonitoredPartialEmailAddressListViewTestCase(BaseCheckViewTestCase):
    list_url = reverse('security:monitored_email_addresses')

    def test_cannot_access_view(self):
        user_data = self.get_user_data(permissions=required_permissions)
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps, user_data=user_data)
            response = self.client.get(self.list_url, follow=True)
            self.assertRedirects(response, reverse('security:dashboard'))

    def test_empty_view(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_my_list_count(rsps)
            rsps.add(
                rsps.GET,
                api_url('/security/monitored-email-addresses/'),
                json={'count': 0, 'results': []},
            )
            response = self.client.get(self.list_url, follow=True)

        content = response.content.decode()
        self.assertIn('You have not yet added any keywords', content)
        self.assertNotIn('mtp-page-list', content)

    def test_view(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_my_list_count(rsps)
            rsps.add(
                rsps.GET,
                api_url('/security/monitored-email-addresses/'),
                json={'count': 2, 'results': ['cat', 'dog']},
            )
            response = self.client.get(self.list_url, follow=True)

        content = response.content.decode()
        self.assertIn('<strong>cat</strong>', content)
        self.assertIn('<strong>dog</strong>', content)
        self.assertIn('2 keywords', content)


class MonitoredPartialEmailAddressAddViewTestCase(BaseCheckViewTestCase):
    add_url = reverse('security:add_monitored_email_address')

    def test_cannot_access_view(self):
        user_data = self.get_user_data(permissions=required_permissions)
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps, user_data=user_data)
            response = self.client.get(self.add_url, follow=True)
            self.assertRedirects(response, reverse('security:dashboard'))

    def test_form_view_without_submission(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            response = self.client.get(self.add_url, follow=True)
        self.assertContains(response, '<!-- security:add_monitored_email_address -->')

    def test_form_view_with_valid_submission(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.POST,
                api_url('/security/monitored-email-addresses/'),
                match=[json_params_matcher(params='Mouse')],
                status=201,
                body=b'mouse',
            )

            # for keyword list after redirect:
            mock_empty_response(rsps, '/security/monitored-email-addresses/')
            self.mock_my_list_count(rsps)

            response = self.client.post(self.add_url, data={'keyword': 'Mouse '}, follow=True)

        self.assertContains(response, '<!-- security:monitored_email_addresses -->')
        content = response.content.decode()
        self.assertIn('“Mouse” has been added', content)

    def test_form_view_with_invalid_submission(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            response = self.client.post(self.add_url, data={'keyword': 'ab'}, follow=True)

        self.assertContains(response, '<!-- security:add_monitored_email_address -->')
        content = response.content.decode()
        self.assertIn('Keyword must be a minimum of 3 characters', content)

    def test_form_view_with_error_response(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.POST,
                api_url('/security/monitored-email-addresses/'),
                status=400,
                json={'keyword': ['Keyword already exists.']},
            )

            # for keyword list after redirect:
            mock_empty_response(rsps, '/security/monitored-email-addresses/')
            self.mock_my_list_count(rsps)

            with silence_logger():
                response = self.client.post(self.add_url, data={'keyword': 'cat'}, follow=True)

        self.assertContains(response, '<!-- security:monitored_email_addresses -->')
        content = response.content.decode()
        self.assertIn('Keyword “cat” could not be added.', content)


class MonitoredPartialEmailAddressDeleteViewTestCase(BaseCheckViewTestCase):
    delete_url = reverse('security:delete_monitored_email_address')

    def test_cannot_access_view(self):
        user_data = self.get_user_data(permissions=required_permissions)
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps, user_data=user_data)
            response = self.client.post(self.delete_url, data={'keyword': 'dog'}, follow=True)
            self.assertRedirects(response, reverse('security:dashboard'))

    def test_delete_keyword(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.DELETE,
                api_url('/security/monitored-email-addresses/dog/'),
                status=204,
                body=b'',
            )

            # for keyword list after redirect:
            mock_empty_response(rsps, '/security/monitored-email-addresses/')
            self.mock_my_list_count(rsps)

            response = self.client.post(self.delete_url, data={'keyword': 'dog'}, follow=True)

        self.assertContains(response, '<!-- security:monitored_email_addresses -->')
        content = response.content.decode()
        self.assertIn('“dog” has been removed', content)

    def test_error_response(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.DELETE,
                api_url('/security/monitored-email-addresses/dog/'),
                status=500,
                body=b'',
            )

            # for keyword list after redirect:
            mock_empty_response(rsps, '/security/monitored-email-addresses/')
            self.mock_my_list_count(rsps)

            with silence_logger():
                response = self.client.post(self.delete_url, data={'keyword': 'dog'}, follow=True)

        self.assertContains(response, '<!-- security:monitored_email_addresses -->')
        content = response.content.decode()
        self.assertIn('Keyword “dog” could not be removed', content)
