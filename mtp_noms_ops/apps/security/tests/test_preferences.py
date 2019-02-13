from django.core.urlresolvers import reverse
from mtp_common.auth import USER_DATA_SESSION_KEY
import responses

from security import hmpps_employee_flag, confirmed_prisons_flag, required_permissions
from security.forms.preferences import ChoosePrisonForm
from security.tests import api_url
from security.tests.test_views import (
    SecurityBaseTestCase, sample_prison_list, sample_prisons
)


class ConfirmPrisonTestCase(SecurityBaseTestCase):
    protected_views = [
        'security:dashboard', 'security:credit_list', 'security:sender_list',
        'security:prisoner_list'
    ]

    @responses.activate
    def test_redirects_when_no_flag(self):
        sample_prison_list()
        self.login(user_data=self.get_user_data(flags=[hmpps_employee_flag]))
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- security:confirm_prisons -->')

    @responses.activate
    def test_does_not_redirect_after_confirmation(self):
        self.login(user_data=self.get_user_data(
            flags=[hmpps_employee_flag, confirmed_prisons_flag])
        )

        response = self.client.get(reverse('security:dashboard'), follow=True)
        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_does_not_redirect_for_other_roles(self):
        self.login(user_data=self.get_user_data(
            flags=[hmpps_employee_flag], roles=['security', 'prison-clerk'])
        )

        response = self.client.get(reverse('security:dashboard'), follow=True)
        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_does_not_redirect_for_user_admin(self):
        self.login(user_data=self.get_user_data(
            flags=[hmpps_employee_flag],
            permissions=required_permissions + ['auth.change_user'])
        )

        response = self.client.get(reverse('security:dashboard'), follow=True)
        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_prison_confirmation(self):
        current_prison = sample_prisons[0]
        new_prison = sample_prisons[1]
        sample_prison_list()
        self.login(user_data=self.get_user_data(
            prisons=[current_prison], flags=[hmpps_employee_flag])
        )
        responses.add(
            responses.PATCH,
            api_url('/users/shall/'),
            json={}
        )
        responses.add(
            responses.GET,
            api_url('/users/shall/'),
            json=self.get_user_data(prisons=[new_prison])
        )
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % confirmed_prisons_flag),
            json={}
        )

        response = self.client.post(reverse('security:confirm_prisons'), data={
            'prisons': [new_prison['nomis_id']],
            'submit_confirm': True
        }, follow=True)

        self.assertContains(response, '<!-- security:confirm_prisons_confirmation -->')
        self.assertIn(
            confirmed_prisons_flag,
            self.client.session[USER_DATA_SESSION_KEY]['flags']
        )
        self.assertIn(
            confirmed_prisons_flag,
            response.context['user'].user_data['flags']
        )
        self.assertEqual(
            [new_prison],
            self.client.session[USER_DATA_SESSION_KEY]['prisons']
        )
        self.assertEqual(
            [new_prison],
            response.context['user'].user_data['prisons']
        )

    @responses.activate
    def test_prison_confirmation_requires_chosen_prisons(self):
        current_prison = sample_prisons[0]
        sample_prison_list()
        self.login(user_data=self.get_user_data(
            prisons=[current_prison], flags=[hmpps_employee_flag])
        )

        response = self.client.post(reverse('security:confirm_prisons'), data={
            'prisons': [],
            'submit_confirm': True
        }, follow=True)

        self.assertContains(response, '<!-- security:confirm_prisons -->')
        self.assertContains(response, ChoosePrisonForm.error_messages['no_prisons_added'])
