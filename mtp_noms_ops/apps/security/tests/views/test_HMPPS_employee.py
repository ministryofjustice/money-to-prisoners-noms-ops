from django.core.urlresolvers import reverse
from mtp_common.auth import USER_DATA_SESSION_KEY
import responses

from security import (
    confirmed_prisons_flag,
    hmpps_employee_flag,
    not_hmpps_employee_flag,
)
from security.tests.utils import api_url
from security.tests.views.test_base import sample_prison_list, SecurityBaseTestCase


class HMPPSEmployeeTestCase(SecurityBaseTestCase):
    protected_views = ['security:dashboard', 'security:credit_list', 'security:sender_list', 'security:prisoner_list']

    @responses.activate
    def test_redirects_when_no_flag(self):
        self.login(user_data=self.get_user_data(flags=[confirmed_prisons_flag]))
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- security:hmpps_employee -->')

    @responses.activate
    def test_non_employee_flag_disallows_entry(self):
        self.login(user_data=self.get_user_data(
            flags=[not_hmpps_employee_flag, confirmed_prisons_flag])
        )
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- security:not_hmpps_employee -->')
            self.assertIn('You can’t use this tool', response.content.decode())

    @responses.activate
    def test_employee_can_access(self):
        self.login(user_data=self.get_user_data(
            flags=[hmpps_employee_flag, confirmed_prisons_flag])
        )

        def assertViewAccessible(view):  # noqa: N802
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- %s -->' % view)

        assertViewAccessible('security:dashboard')
        sample_prison_list()
        assertViewAccessible('security:credit_list')

    @responses.activate
    def test_employee_flag_set(self):
        self.login(user_data=self.get_user_data(
            flags=['abc', confirmed_prisons_flag])
        )
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % hmpps_employee_flag),
            json={}
        )
        response = self.client.post(reverse('security:hmpps_employee'), data={
            'confirmation': 'yes',
        }, follow=True)
        self.assertContains(response, '<!-- security:dashboard -->')
        self.assertIn(hmpps_employee_flag, self.client.session[USER_DATA_SESSION_KEY]['flags'])
        self.assertIn(hmpps_employee_flag, response.context['user'].user_data['flags'])

    @responses.activate
    def test_redirects_to_referrer(self):
        self.login(user_data=self.get_user_data(flags=[confirmed_prisons_flag]))
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % hmpps_employee_flag),
            json={}
        )
        sample_prison_list()
        response = self.client.post(reverse('security:hmpps_employee'), data={
            'confirmation': 'yes',
            'next': reverse('security:prisoner_list'),
        }, follow=True)
        self.assertContains(response, '<!-- security:prisoner_list -->')

    @responses.activate
    def test_non_employee_flag_set(self):
        self.login(user_data=self.get_user_data(
            flags=['123', confirmed_prisons_flag])
        )
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % not_hmpps_employee_flag),
            json={}
        )
        responses.add(
            responses.DELETE,
            api_url('/users/shall/'),
            json={}
        )
        response = self.client.post(reverse('security:hmpps_employee'), data={
            'confirmation': 'no',
        }, follow=True)
        self.assertContains(response, '<!-- security:not_hmpps_employee -->')
        self.assertIn('You can’t use this tool', response.content.decode())
