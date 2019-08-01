import json

from django.core.urlresolvers import reverse
import responses

from security import (
    hmpps_employee_flag,
    confirmed_prisons_flag,
    notifications_pilot_flag,
)
from security.models import EmailNotifications
from security.tests.utils import api_url
from security.tests.views.test_base import SecurityBaseTestCase


class SettingsTestCase(SecurityBaseTestCase):
    def test_cannot_see_email_notifications_switch_without_pilot_flag(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            response = self.client.get(reverse('settings'), follow=True)
        self.assertNotContains(response, 'Email notifications')

    def test_can_turn_on_email_notifications_switch_with_pilot_flag(self):
        with responses.RequestsMock() as rsps:
            self.login(user_data=self.get_user_data(flags=[
                notifications_pilot_flag, hmpps_employee_flag, confirmed_prisons_flag,
            ]), rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url('/emailpreferences/'),
                json={'frequency': EmailNotifications.never},
            )
            response = self.client.get(reverse('settings'), follow=True)
            self.assertContains(response, 'not currently receiving email notifications')

            rsps.add(
                rsps.POST,
                api_url('/emailpreferences/'),
            )
            rsps.replace(
                rsps.GET,
                api_url('/emailpreferences/'),
                json={'frequency': EmailNotifications.daily},
            )
            response = self.client.post(reverse('settings'), data={'email_notifications': 'True'}, follow=True)
            self.assertNotContains(response, 'not currently receiving email notifications')

            last_post_call = list(filter(lambda call: call.request.method == rsps.POST, rsps.calls))[-1]
            last_request_body = json.loads(last_post_call.request.body)
            self.assertDictEqual(last_request_body, {'frequency': 'daily'})

    def test_can_turn_off_email_notifications_switch_with_pilot_flag(self):
        with responses.RequestsMock() as rsps:
            self.login(user_data=self.get_user_data(flags=[
                notifications_pilot_flag, hmpps_employee_flag, confirmed_prisons_flag,
            ]), rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url('/emailpreferences/'),
                json={'frequency': EmailNotifications.daily},
            )
            response = self.client.get(reverse('settings'), follow=True)
            self.assertNotContains(response, 'not currently receiving email notifications')

            rsps.add(
                rsps.POST,
                api_url('/emailpreferences/'),
            )
            rsps.replace(
                rsps.GET,
                api_url('/emailpreferences/'),
                json={'frequency': EmailNotifications.never},
            )
            response = self.client.post(reverse('settings'), data={'email_notifications': 'False'}, follow=True)
            self.assertContains(response, 'not currently receiving email notifications')

            last_post_call = list(filter(lambda call: call.request.method == rsps.POST, rsps.calls))[-1]
            last_request_body = json.loads(last_post_call.request.body)
            self.assertDictEqual(last_request_body, {'frequency': 'never'})
