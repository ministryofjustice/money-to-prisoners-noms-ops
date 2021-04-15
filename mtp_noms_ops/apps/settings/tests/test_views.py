import json

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.urls import reverse
from django.utils.html import escape
from mtp_common.auth import USER_DATA_SESSION_KEY
import responses

from security import (
    confirmed_prisons_flag,
    hmpps_employee_flag,
    required_permissions,
    provided_job_info_flag,
)
from security.models import EmailNotifications
from security.tests import api_url
from security.tests.test_views import (
    mock_prison_response,
    SAMPLE_PRISONS,
    SecurityBaseTestCase,
)


class ConfirmPrisonTestCase(SecurityBaseTestCase):
    protected_views = [
        'security:credit_list',
        'security:dashboard',
        'security:prisoner_list',
        'security:sender_list',
    ]

    @responses.activate
    def test_redirects_when_no_flag(self):
        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[
                    hmpps_employee_flag,
                ],
            ),
        )
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- confirm_prisons -->')

    @responses.activate
    def test_does_not_redirect_after_confirmation(self):
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[hmpps_employee_flag, confirmed_prisons_flag, provided_job_info_flag]
            )
        )
        response = self.client.get(reverse('security:dashboard'), follow=True)
        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_does_not_redirect_for_other_roles(self):
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[hmpps_employee_flag, provided_job_info_flag],
                roles=['security', 'prison-clerk']
            )
        )
        response = self.client.get(reverse('security:dashboard'), follow=True)
        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_does_not_redirect_for_user_admin(self):
        responses.add(
            responses.GET,
            api_url('/requests') + '?page_size=1',
            json={'count': 0},
            status=200,
        )

        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[hmpps_employee_flag, provided_job_info_flag],
                permissions=required_permissions + ['auth.change_user']
            )
        )
        response = self.client.get(reverse('security:dashboard'), follow=True)
        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_prison_confirmation(self):
        current_prison = SAMPLE_PRISONS[0]
        new_prison = SAMPLE_PRISONS[1]
        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                prisons=[current_prison], flags=[hmpps_employee_flag]
            )
        )
        responses.add(
            responses.PATCH,
            api_url('/users/shall/'),
            json={}
        )
        responses.replace(
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
        current_prison = SAMPLE_PRISONS[0]
        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                prisons=[current_prison], flags=[hmpps_employee_flag]
            )
        )
        responses.add(
            responses.PATCH,
            api_url('/users/shall/'),
            json={}
        )
        responses.replace(
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
    """
    Tests related to the change prison views.
    """

    def _mock_save_prisons_responses(self, new_prisons):
        """
        Mocks all responses related to saving the form successfully.
        """
        responses.add(
            responses.PATCH,
            api_url('/users/shall/'),
            json={},
        )
        responses.replace(
            responses.GET,
            api_url('/users/shall/'),
            json=self.get_user_data(
                prisons=new_prisons,
            ),
        )
        responses.add(
            responses.PUT,
            api_url(f'/users/shall/flags/{confirmed_prisons_flag}/'),
            json={},
        )

    @responses.activate
    def test_change_prisons(self):
        """
        Test changing my prisons' data by replacing an existing previously selected
        prison with a new one.
        """
        current_prison = SAMPLE_PRISONS[0]
        new_prison = SAMPLE_PRISONS[1]
        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                prisons=[current_prison], flags=[
                    hmpps_employee_flag,
                    confirmed_prisons_flag
                ]
            )
        )

        responses.add(
            responses.GET,
            api_url('/emailpreferences/'),
            json={'frequency': EmailNotifications.never},
        )
        response = self.client.get(reverse('settings'), follow=True)
        self.assertContains(response, escape(current_prison['name']))

        self._mock_save_prisons_responses([new_prison])

        response = self.client.post(reverse('change_prisons'), data={
            'prison_0': new_prison['nomis_id'],
            'submit_save': True
        }, follow=True)
        self.assertContains(response, escape(new_prison['name']))

    @responses.activate
    def test_add_prison(self):
        """
        Test that clicking on 'Add another prison' redirects to the same page
        with a new textfield for the new prison added.
        Note: the test does not save the form but it only tests its initialisation.
        """
        current_prison = SAMPLE_PRISONS[0]
        new_prison = SAMPLE_PRISONS[1]
        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                prisons=[current_prison], flags=[
                    hmpps_employee_flag,
                    confirmed_prisons_flag
                ]
            )
        )

        response = self.client.post(reverse('change_prisons'), data={
            'prison_0': new_prison['nomis_id'],
            'submit_add': True
        }, follow=True)
        self.assertContains(response, 'name="prison_0"')
        self.assertContains(response, 'name="prison_1"')

    @responses.activate
    def test_remove_prison(self):
        """
        Test that clicking on 'Remove' redirects to the same page with that textfield removed.
        Note: the test does not save the form but it only tests its initialisation.
        """
        current_prison = SAMPLE_PRISONS[0]
        new_prison = SAMPLE_PRISONS[1]
        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                prisons=[current_prison], flags=[
                    hmpps_employee_flag,
                    confirmed_prisons_flag
                ]
            )
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
        """
        Test that clicking on 'Add all prisons' redirects to the 'All Prisons' version of the page.
        Note: the test does not save the form but it only tests its initialisation.
        """
        current_prison = SAMPLE_PRISONS[0]
        new_prison = SAMPLE_PRISONS[1]
        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                prisons=[current_prison], flags=[
                    hmpps_employee_flag,
                    confirmed_prisons_flag
                ]
            )
        )

        response = self.client.post(reverse('change_prisons'), data={
            'prison_0': new_prison['nomis_id'],
            'submit_all': True
        }, follow=True)
        self.assertNotContains(response, 'name="prison_0"')
        self.assertContains(response, 'All prisons')

    @responses.activate
    def test_not_all_prisons(self):
        """
        Test that clicking on 'Remove all prisons' redirects to the default version of the page
        (not the 'All Prison' one).
        Note: the test does not save the form but it only tests its initialisation.
        """
        current_prison = SAMPLE_PRISONS[0]
        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                prisons=[current_prison], flags=[
                    hmpps_employee_flag,
                    confirmed_prisons_flag
                ]
            )
        )

        response = self.client.post(reverse('change_prisons'), data={
            'all_prisons': True,
            'submit_notall': True
        }, follow=True)
        self.assertContains(response, 'name="prison_1"')
        self.assertNotContains(response, 'All prisons')

    @responses.activate
    def test_next_url(self):
        """
        Test that if the next param is passed in, the view redirects to it after saving the changes.
        """
        current_prison = SAMPLE_PRISONS[0]
        new_prison = SAMPLE_PRISONS[1]

        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                prisons=[current_prison],
            ),
        )

        self._mock_save_prisons_responses([new_prison])

        next_page = reverse('root')
        response = self.client.post(
            f"{reverse('change_prisons')}?{REDIRECT_FIELD_NAME}={next_page}",
            data={
                'prison_0': new_prison['nomis_id'],
                'submit_save': True,
            },
        )
        self.assertRedirects(response, next_page, target_status_code=302)

    @responses.activate
    def test_invalid_next_url(self):
        """
        Test that if the passed in next param is not in the allowed hosts list,
        the view redirects to the default view after saving the changes instead.
        """
        current_prison = SAMPLE_PRISONS[0]
        new_prison = SAMPLE_PRISONS[1]

        mock_prison_response()
        self.login(
            responses,
            user_data=self.get_user_data(
                prisons=[current_prison],
            ),
        )

        self._mock_save_prisons_responses([new_prison])
        responses.add(
            responses.GET,
            api_url('/emailpreferences/'),
            json={'frequency': EmailNotifications.never},
        )

        response = self.client.post(
            f"{reverse('change_prisons')}?{REDIRECT_FIELD_NAME}=http://google.co.uk",
            data={
                'prison_0': new_prison['nomis_id'],
                'submit_save': True,
            },
        )
        self.assertRedirects(response, reverse('settings'))
