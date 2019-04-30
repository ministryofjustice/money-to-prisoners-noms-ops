import json

from django.core.urlresolvers import reverse
from django.utils.html import escape
from mtp_common.auth import USER_DATA_SESSION_KEY
import responses

from security import (
    hmpps_employee_flag, confirmed_prisons_flag, required_permissions
)
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
        self.login(user_data=self.get_user_data(
            flags=[hmpps_employee_flag])
        )
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- confirm_prisons -->')

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
            flags=[hmpps_employee_flag],
            roles=['security', 'prison-clerk'])
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

        response = self.client.post(reverse('confirm_prisons'), data={
            'prisons': [new_prison['nomis_id']]
        }, follow=True)

        self.assertEqual(
            set(
                p['nomis_id'] for p in
                json.loads(responses.calls[-3].request.body.decode())['prisons']
            ),
            set([new_prison['nomis_id']])
        )
        self.assertContains(response, '<!-- confirm_prisons_confirmation -->')
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
    def test_prison_confirmation_all_prisons(self):
        current_prison = sample_prisons[0]
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
            json=self.get_user_data(prisons=[])
        )
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % confirmed_prisons_flag),
            json={}
        )

        response = self.client.post(reverse('confirm_prisons'), data={
            'prisons': []
        }, follow=True)

        self.assertEqual(
            set(
                p['nomis_id'] for p in
                json.loads(responses.calls[-3].request.body.decode())['prisons']
            ),
            set([])
        )
        self.assertContains(response, '<!-- confirm_prisons_confirmation -->')
        self.assertIn(
            confirmed_prisons_flag,
            self.client.session[USER_DATA_SESSION_KEY]['flags']
        )
        self.assertIn(
            confirmed_prisons_flag,
            response.context['user'].user_data['flags']
        )
        self.assertEqual(
            [],
            self.client.session[USER_DATA_SESSION_KEY]['prisons']
        )
        self.assertEqual(
            [],
            response.context['user'].user_data['prisons']
        )


class ChangePrisonTestCase(SecurityBaseTestCase):

    @responses.activate
    def test_change_prisons(self):
        current_prison = sample_prisons[0]
        new_prison = sample_prisons[1]
        sample_prison_list()
        self.login(user_data=self.get_user_data(
            prisons=[current_prison], flags=[
                hmpps_employee_flag,
                confirmed_prisons_flag
            ])
        )

        response = self.client.get(reverse('settings'), follow=True)
        self.assertContains(response, escape(current_prison['name']))

        responses.add(
            responses.PATCH,
            api_url('/users/shall/'),
            json={}
        )
        responses.add(
            responses.GET,
            api_url('/users/shall/'),
            json=self.get_user_data(
                prisons=[new_prison],
                flags=[
                    hmpps_employee_flag,
                    confirmed_prisons_flag
                ]
            )
        )
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % confirmed_prisons_flag),
            json={}
        )

        response = self.client.post(reverse('change_prisons'), data={
            'prison_0': new_prison['nomis_id'],
            'submit_save': True
        }, follow=True)
        self.assertContains(response, escape(new_prison['name']))

    @responses.activate
    def test_add_prison(self):
        current_prison = sample_prisons[0]
        new_prison = sample_prisons[1]
        sample_prison_list()
        self.login(user_data=self.get_user_data(
            prisons=[current_prison], flags=[
                hmpps_employee_flag,
                confirmed_prisons_flag
            ])
        )

        response = self.client.post(reverse('change_prisons'), data={
            'prison_0': new_prison['nomis_id'],
            'submit_add': True
        }, follow=True)
        self.assertContains(response, 'name="prison_0"')
        self.assertContains(response, 'name="prison_1"')

    @responses.activate
    def test_remove_prison(self):
        current_prison = sample_prisons[0]
        new_prison = sample_prisons[1]
        sample_prison_list()
        self.login(user_data=self.get_user_data(
            prisons=[current_prison], flags=[
                hmpps_employee_flag,
                confirmed_prisons_flag
            ])
        )

        response = self.client.post(reverse('change_prisons'), data={
            'prison_0': current_prison['nomis_id'],
            'prison_1': new_prison['nomis_id'],
            'submit_remove_prison_0': True
        }, follow=True)
        self.assertNotContains(response, 'name="prison_0"')
        self.assertContains(response, 'name="prison_1"')

    @responses.activate
    def test_add_all_prisons(self):
        current_prison = sample_prisons[0]
        new_prison = sample_prisons[1]
        sample_prison_list()
        self.login(user_data=self.get_user_data(
            prisons=[current_prison], flags=[
                hmpps_employee_flag,
                confirmed_prisons_flag
            ])
        )

        response = self.client.post(reverse('change_prisons'), data={
            'prison_0': new_prison['nomis_id'],
            'submit_all': True
        }, follow=True)
        self.assertNotContains(response, 'name="prison_0"')
        self.assertContains(response, 'All prisons')

    @responses.activate
    def test_not_all_prisons(self):
        current_prison = sample_prisons[0]
        sample_prison_list()
        self.login(user_data=self.get_user_data(
            prisons=[current_prison], flags=[
                hmpps_employee_flag,
                confirmed_prisons_flag
            ])
        )

        response = self.client.post(reverse('change_prisons'), data={
            'all_prisons': True,
            'submit_notall': True
        }, follow=True)
        self.assertContains(response, 'name="prison_1"')
        self.assertNotContains(response, 'All prisons')
