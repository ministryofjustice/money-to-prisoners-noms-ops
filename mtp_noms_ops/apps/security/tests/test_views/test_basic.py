import datetime
import json
import logging

from django.http import QueryDict
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from mtp_common.auth import USER_DATA_SESSION_KEY
from mtp_common.test_utils import silence_logger
import responses

from security import (
    confirmed_prisons_flag,
    hmpps_employee_flag,
    not_hmpps_employee_flag,
    provided_job_info_flag,
)
from security.constants import SECURITY_FORMS_DEFAULT_PAGE_SIZE
from security.models import EmailNotifications
from security.tests import api_url
from security.tests.test_views import SecurityBaseTestCase, SAMPLE_PRISONS, mock_prison_response, no_saved_searches


def mock_post_for_job_info_endpoint(rsps=None):
    rsps = rsps or responses
    rsps.add(
        rsps.POST,
        api_url('/job-information/'),
        json={
            'job_title': 'Evidence collator',
            'prison_estate': 'National',
            'tasks': 'Inmate Processing'
        },
    )


class LocaleTestCase(SecurityBaseTestCase):
    def test_locale_switches_based_on_browser_language(self):
        languages = (
            ('*', 'en-gb'),
            ('en', 'en-gb'),
            ('en-gb', 'en-gb'),
            ('en-GB, en, *', 'en-gb'),
            ('cy', 'cy'),
            ('cy, en-GB, en, *', 'cy'),
            ('en, cy, *', 'en-gb'),
            ('es', 'en-gb'),
        )
        with silence_logger(name='django.request', level=logging.ERROR):
            for accept_language, expected_slug in languages:
                response = self.client.get('/', HTTP_ACCEPT_LANGUAGE=accept_language)
                self.assertRedirects(response, '/%s/' % expected_slug, fetch_redirect_response=False)
                response = self.client.get('/login/', HTTP_ACCEPT_LANGUAGE=accept_language)
                self.assertRedirects(response, '/%s/login/' % expected_slug, fetch_redirect_response=True)


class SecurityDashboardViewsTestCase(SecurityBaseTestCase):
    @responses.activate
    def test_can_access_security_dashboard(self):
        response = self.login(responses)
        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_cannot_access_prisoner_location_admin(self):
        self.login(responses)
        no_saved_searches()
        response = self.client.get(reverse('location_file_upload'), follow=True)
        self.assertNotContains(response, '<!-- location_file_upload -->')
        self.assertContains(response, '<!-- security:dashboard -->')


class HMPPSEmployeeTestCase(SecurityBaseTestCase):
    protected_views = [
        'security:credit_list',
        'security:dashboard',
        'security:disbursement_list',
        'security:prisoner_list',
        'security:sender_list',
    ]

    @responses.activate
    def test_redirects_when_no_flag(self):
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[
                    confirmed_prisons_flag,
                ],
            ),
        )
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- security:hmpps_employee -->')

    @responses.activate
    def test_non_employee_flag_disallows_entry(self):
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[
                    confirmed_prisons_flag,
                    not_hmpps_employee_flag,
                ],
            ),
        )
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- security:not_hmpps_employee -->')
            self.assertIn('You can’t use this tool', response.content.decode())

    @responses.activate
    def test_employee_can_access(self):
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[
                    confirmed_prisons_flag,
                    hmpps_employee_flag,
                    provided_job_info_flag,
                ]
            )
        )

        def assertViewAccessible(view):  # noqa: N802
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- %s -->' % view)

        assertViewAccessible('security:dashboard')
        mock_prison_response()
        assertViewAccessible('security:credit_list')

    @responses.activate
    def test_employee_flag_set(self):
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=['abc', confirmed_prisons_flag, provided_job_info_flag]
            )
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
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[
                    confirmed_prisons_flag,
                    provided_job_info_flag,
                ],
            ),
        )
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % hmpps_employee_flag),
            json={}
        )
        mock_prison_response()
        response = self.client.post(reverse('security:hmpps_employee'), data={
            'confirmation': 'yes',
            'next': reverse('security:prisoner_list'),
        }, follow=True)
        self.assertContains(response, '<!-- security:prisoner_list -->')

    @responses.activate
    def test_non_employee_flag_set(self):
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=['123', confirmed_prisons_flag]
            )
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


class JobInformationViewTestCase(SecurityBaseTestCase):
    protected_views = [
        'security:credit_list',
        'security:dashboard',
        'security:disbursement_list',
        'security:prisoner_list',
        'security:sender_list',
    ]

    @responses.activate
    def test_redirects_when_provided_job_info_flag_is_missing(self):
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[
                    confirmed_prisons_flag,
                    hmpps_employee_flag,
                ],
            ),
        )
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- job_information -->')

    @responses.activate
    def test_can_view_app_when_user_has_provided_job_info_flag(self):
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[
                    confirmed_prisons_flag,
                    hmpps_employee_flag,
                    provided_job_info_flag,
                ]
            ),
        )
        response = self.client.get(reverse('security:dashboard'), follow=True)
        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_successful_form_post(self):
        mock_post_for_job_info_endpoint()
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[confirmed_prisons_flag, hmpps_employee_flag]
            )
        )
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % provided_job_info_flag),
            json={}
        )

        response = self.client.post(reverse('job_information'), data={
            'job_title': 'Evidence collator',
            'prison_estate': 'National',
            'tasks': 'yas sir'
        }, follow=True)

        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_unsuccessful_form_post(self):
        mock_post_for_job_info_endpoint()
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[
                    confirmed_prisons_flag,
                    hmpps_employee_flag
                ]
            )
        )
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % provided_job_info_flag),
            json={}
        )

        response = self.client.post(reverse('job_information'), data={
            'job_title': '',
            'prison_estate': '',
            'tasks': ''
        }, follow=True)

        self.assertContains(response, '<!-- job_information -->')
        self.assertContains(response, 'This field is required')

    @responses.activate
    def test_form_adds_provided_job_info_flag(self):
        mock_post_for_job_info_endpoint()
        self.login(
            responses,
            user_data=self.get_user_data(
                flags=[
                    confirmed_prisons_flag,
                    hmpps_employee_flag
                ]
            )
        )
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % provided_job_info_flag),
            json={}
        )

        response = self.client.post(reverse('job_information'), data={
            'job_title': 'Evidence collator',
            'prison_estate': 'National',
            'tasks': 'yas sir'
        }, follow=True)

        self.assertIn(provided_job_info_flag, response.context['user'].user_data['flags'])


class PolicyChangeViewTestCase(SecurityBaseTestCase):
    @responses.activate
    @override_settings(NOVEMBER_SECOND_CHANGES_LIVE=False)
    def test_displays_policy_warning_page_before_policy_change(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
        response = self.client.get(reverse('security:policy_change'), follow=True)
        self.assertContains(response, 'policy-change-warning')

    @responses.activate
    @override_settings(NOVEMBER_SECOND_CHANGES_LIVE=True)
    def test_displays_policy_update_page_after_policy_change(self):
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
        response = self.client.get(reverse('security:policy_change'), follow=True)
        self.assertContains(response, 'policy-change-info')


class SettingsTestCase(SecurityBaseTestCase):
    def test_can_turn_on_email_notifications_switch(self):
        with responses.RequestsMock() as rsps:
            self.login(
                rsps,
                user_data=self.get_user_data(flags=[
                    hmpps_employee_flag, confirmed_prisons_flag,
                    provided_job_info_flag,
                ])
            )
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

    def test_can_turn_off_email_notifications_switch(self):
        with responses.RequestsMock() as rsps:
            self.login(
                rsps,
                user_data=self.get_user_data(
                    flags=[
                        hmpps_employee_flag, confirmed_prisons_flag,
                        provided_job_info_flag,
                    ]
                )
            )
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


class PrisonSwitcherTestCase(SecurityBaseTestCase):
    """
    Tests related to the prison switcher area on the top of some pages.
    The prison switcher area shows the prisons that the user selected in the settings
    page with a link to change this.
    """

    @classmethod
    def _mock_api_responses(cls):
        no_saved_searches()
        mock_prison_response()
        responses.add(
            responses.GET,
            api_url('/senders/'),
            json={},
        )

    @responses.activate
    def test_with_many_prisons(self):
        """
        Test that if the user has more than 4 prisons in settings, only the first ones are
        shown in the prison switcher area to avoid long text.
        """
        self._mock_api_responses()
        prisons = [
            {
                **SAMPLE_PRISONS[0],
                'name': f'Prison {index}',
            } for index in range(1, 11)
        ]
        self.login(
            responses,
            user_data=self.get_user_data(prisons=prisons),
        )
        response = self.client.get(reverse('security:sender_list'))
        self.assertContains(
            response,
            'Prison 1, Prison 2, Prison 3, Prison 4',
        )
        self.assertContains(
            response,
            ' and 6 more',
        )

    @responses.activate
    def test_with_fewer_prisons(self):
        """
        Test that if the user has less than 4 prisons in settings,
        they are all shown in the prison switcher area.
        """
        self._mock_api_responses()
        prisons = [
            {
                **SAMPLE_PRISONS[0],
                'name': f'Prison {index}',
            } for index in range(1, 3)
        ]
        self.login(
            responses,
            user_data=self.get_user_data(prisons=prisons),
        )
        response = self.client.get(reverse('security:sender_list'))
        self.assertContains(
            response,
            'Prison 1, Prison 2',
        )

        self.assertNotContains(
            response,
            'Prison 3',
        )

    @responses.activate
    def test_sees_all_prisons(self):
        """
        Test that if the user hasn't specified any prisons in settings, it means that he/she can
        see all prisons so the text 'All prisons' is known in the prison switcher area.
        """
        self._mock_api_responses()
        self.login(
            responses,
            user_data=self.get_user_data(prisons=[]),
        )
        response = self.client.get(reverse('security:sender_list'))
        self.assertContains(
            response,
            'All prisons',
        )


class PinnedProfileTestCase(SecurityBaseTestCase):
    def login_test_searches(self, rsps, follow=True):
        return self._login(rsps, follow=follow)

    @responses.activate
    def test_pinned_profiles_on_dashboard(self):
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 2,
                'results': [
                    {
                        'id': 1,
                        'description': 'Saved search 1',
                        'endpoint': '/prisoners/1/credits',
                        'last_result_count': 2,
                        'site_url': '/en-gb/security/prisoners/1/',
                        'filters': []
                    },
                    {
                        'id': 2,
                        'description': 'Saved search 2',
                        'endpoint': '/senders/1/credits',
                        'last_result_count': 3,
                        'site_url': '/en-gb/security/senders/1/',
                        'filters': []
                    }
                ]
            },
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/1/credits/'),
            json={
                'count': 5,
                'results': []
            },
        )
        responses.add(
            responses.GET,
            api_url('/senders/1/credits/'),
            json={
                'count': 10,
                'results': []
            },
        )
        response = self.login_test_searches(rsps=responses)

        self.assertContains(response, 'Saved search 1')
        self.assertContains(response, 'Saved search 2')
        self.assertContains(response, '3 new credits')
        self.assertContains(response, '7 new credits')

    @responses.activate
    def test_removes_invalid_saved_searches(self):
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 2,
                'results': [
                    {
                        'id': 1,
                        'description': 'Saved search 1',
                        'endpoint': '/prisoners/1/credits',
                        'last_result_count': 2,
                        'site_url': '/en-gb/security/prisoners/1/',
                        'filters': []
                    },
                    {
                        'id': 2,
                        'description': 'Saved search 2',
                        'endpoint': '/senders/1/credits',
                        'last_result_count': 3,
                        'site_url': '/en-gb/security/senders/1/',
                        'filters': []
                    }
                ]
            },
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/1/credits/'),
            json={
                'count': 5,
                'results': []
            },
        )
        responses.add(
            responses.GET,
            api_url('/senders/1/credits/'),
            status=404,
        )
        responses.add(
            responses.DELETE,
            api_url('/searches/2/'),
            status=201,
        )
        response = self.login_test_searches(rsps=responses)

        self.assertContains(response, 'Saved search 1')
        self.assertNotContains(response, 'Saved search 2')
        self.assertContains(response, '3 new credits')


class NotificationsTestCase(SecurityBaseTestCase):
    def login(self, rsps):
        super().login(
            rsps,
            user_data=self.get_user_data(
                flags=[
                    hmpps_employee_flag, confirmed_prisons_flag, provided_job_info_flag,
                ]
            )
        )

    def test_no_notifications_not_monitoring(self):
        """
        Expect to see a message if you're not monitoring anything and have no notifications
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + f'?rule=MONP&rule=MONS&offset=0&limit={SECURITY_FORMS_DEFAULT_PAGE_SIZE}',
                json={'count': 0, 'newest': None, 'oldest': None},
                match_querystring=True
            )
            rsps.add(
                rsps.GET,
                api_url('/monitored/'),
                json={'count': 0},
            )
            rsps.add(
                rsps.GET,
                api_url('/events/'),
                json={'count': 0, 'results': []},
            )
            response = self.client.get(reverse('security:notification_list'))
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('You’re not monitoring anything at the moment', response_content)
        self.assertIn('0 results', response_content)

    def test_no_notifications_but_monitoring(self):
        """
        Expect to see nothing interesting if monitoring some profile, but have no notifications
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + f'?rule=MONP&rule=MONS&offset=0&limit={SECURITY_FORMS_DEFAULT_PAGE_SIZE}',
                json={'count': 0, 'newest': None, 'oldest': None},
                match_querystring=True
            )
            rsps.add(
                rsps.GET,
                api_url('/monitored/'),
                json={'count': 3},
            )
            rsps.add(
                rsps.GET,
                api_url('/events/'),
                json={'count': 0, 'results': []},
            )
            response = self.client.get(reverse('security:notification_list'))
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertNotIn('You’re not monitoring anything at the moment', response_content)
        self.assertIn('0 results', response_content)

    def test_notifications_not_monitoring(self):
        """
        Expect to see a message if you're not monitoring anything even if you have notifications
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + f'?rule=MONP&rule=MONS&offset=0&limit={SECURITY_FORMS_DEFAULT_PAGE_SIZE}',
                json={'count': 1, 'newest': '2019-07-15', 'oldest': '2019-07-15'},
                match_querystring=True
            )
            rsps.add(
                rsps.GET,
                api_url('/monitored/'),
                json={'count': 0},
            )
            rsps.add(
                rsps.GET,
                api_url('/events/'),
                json={'count': 1, 'results': [
                    {
                        'id': 1,
                        'rule': 'MONP',
                        'triggered_at': '2019-07-15T10:00:00Z',
                        'credit_id': 1, 'disbursement_id': None,
                        'sender_profile': None, 'recipient_profile': None,
                        'prisoner_profile': {
                            'id': 1, 'prisoner_name': 'JAMES HALLS', 'prisoner_number': 'A1409AE',
                        },
                    }
                ]},
            )
            response = self.client.get(reverse('security:notification_list'))
            request_url = rsps.calls[-2].request.url
            request_query = request_url.split('?', 1)[1]
            request_query = QueryDict(request_query)
            self.assertEqual(request_query['triggered_at__gte'], '2019-07-15')
            self.assertEqual(request_query['triggered_at__lt'], '2019-07-16')
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('You’re not monitoring anything at the moment', response_content)
        self.assertIn('1 result', response_content)
        self.assertIn('1 transaction', response_content)
        self.assertIn('JAMES HALLS (A1409AE)', response_content)

    def test_notifications_but_monitoring(self):
        """
        Expect to see a list of notifications when some exist
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + f'?rule=MONP&rule=MONS&offset=0&limit={SECURITY_FORMS_DEFAULT_PAGE_SIZE}',
                json={'count': 1, 'newest': '2019-07-15', 'oldest': '2019-07-15'},
                match_querystring=True
            )
            rsps.add(
                rsps.GET,
                api_url('/monitored/'),
                json={'count': 3},
            )
            rsps.add(
                rsps.GET,
                api_url('/events/'),
                json={'count': 1, 'results': [
                    {
                        'id': 1,
                        'rule': 'MONP',
                        'triggered_at': '2019-07-15T10:00:00Z',
                        'credit_id': 1, 'disbursement_id': None,
                        'sender_profile': None, 'recipient_profile': None,
                        'prisoner_profile': {
                            'id': 1, 'prisoner_name': 'JAMES HALLS', 'prisoner_number': 'A1409AE',
                        },
                    }
                ]},
            )
            response = self.client.get(reverse('security:notification_list'))
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertNotIn('You’re not monitoring anything at the moment', response_content)
        self.assertIn('1 result', response_content)
        self.assertIn('1 transaction', response_content)
        self.assertIn('JAMES HALLS (A1409AE)', response_content)

    def test_notification_pages(self):
        """
        Expect the correct number of pages if there are many notifications
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + f'?rule=MONP&rule=MONS&offset=0&limit={SECURITY_FORMS_DEFAULT_PAGE_SIZE}',
                json={'count': 32, 'newest': '2019-07-15', 'oldest': '2019-06-21'},
                match_querystring=True
            )
            rsps.add(
                rsps.GET,
                api_url('/monitored/'),
                json={'count': 3},
            )
            rsps.add(
                rsps.GET,
                api_url('/events/'),
                json={'count': 25, 'results': [
                    {
                        'id': 1 + days,
                        'rule': 'MONP',
                        'triggered_at': (
                            timezone.make_aware(
                                datetime.datetime(2019, 7, 15, 10) - datetime.timedelta(days)
                            ).isoformat()
                        ),
                        'credit_id': 1 + days, 'disbursement_id': None,
                        'sender_profile': None, 'recipient_profile': None,
                        'prisoner_profile': {
                            'id': 1, 'prisoner_name': 'JAMES HALLS', 'prisoner_number': 'A1409AE',
                        },
                    }
                    for days in range(0, 25)
                ]},
            )
            response = self.client.get(reverse('security:notification_list'))
            request_url = rsps.calls[-2].request.url
            request_query = request_url.split('?', 1)[1]
            request_query = QueryDict(request_query)
            self.assertEqual(request_query['triggered_at__gte'], '2019-06-21')
            self.assertEqual(request_query['triggered_at__lt'], '2019-07-16')
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('32 results', response_content)
        self.assertIn('Page 1 of 2.', response_content)

    def test_notification_grouping(self):
        """
        Expect notifications to be grouped by connected profile
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + f'?rule=MONP&rule=MONS&offset=0&limit={SECURITY_FORMS_DEFAULT_PAGE_SIZE}',
                json={'count': 1, 'newest': '2019-07-15', 'oldest': '2019-07-15'},
                match_querystring=True
            )
            rsps.add(
                rsps.GET,
                api_url('/monitored/'),
                json={'count': 4},
            )
            rsps.add(
                rsps.GET,
                api_url('/events/'),
                json={'count': 6, 'results': [
                    {
                        'id': 1,
                        'rule': 'MONP',
                        'triggered_at': '2019-07-15T10:00:00Z',
                        'credit_id': 1, 'disbursement_id': None,
                        'sender_profile': None, 'recipient_profile': None,
                        'prisoner_profile': {
                            'id': 1, 'prisoner_name': 'JAMES HALLS', 'prisoner_number': 'A1409AE',
                        },
                    },
                    {
                        'id': 2,
                        'rule': 'MONS',
                        'triggered_at': '2019-07-15T09:00:00Z',
                        'credit_id': 2, 'disbursement_id': None,
                        'prisoner_profile': None, 'recipient_profile': None,
                        'sender_profile': {
                            'id': 1, 'bank_transfer_details': [{'sender_name': 'Mary Halls'}],
                        },
                    },
                    {
                        'id': 3,
                        'rule': 'MONP',
                        'triggered_at': '2019-07-15T08:00:00Z',
                        'credit_id': 3, 'disbursement_id': None,
                        'sender_profile': None, 'recipient_profile': None,
                        'prisoner_profile': {
                            'id': 2, 'prisoner_name': 'JILLY HALL', 'prisoner_number': 'A1401AE',
                        },
                    },
                    {
                        'id': 4,
                        'rule': 'MONP',
                        'triggered_at': '2019-07-15T07:00:00Z',
                        'credit_id': None, 'disbursement_id': 1,
                        'sender_profile': None, 'recipient_profile': None,
                        'prisoner_profile': {
                            'id': 1, 'prisoner_name': 'JAMES HALLS', 'prisoner_number': 'A1409AE',
                        },
                    },
                    {
                        'id': 5,
                        'rule': 'MONS',
                        'triggered_at': '2019-07-15T06:00:00Z',
                        'credit_id': 5, 'disbursement_id': None,
                        'prisoner_profile': None, 'recipient_profile': None,
                        'sender_profile': {
                            'id': 1, 'bank_transfer_details': [{'sender_name': 'Mary Halls'}],
                        },
                    },
                    {
                        'id': 6,
                        'rule': 'MONS',
                        'triggered_at': '2019-07-15T05:00:00Z',
                        'credit_id': 6, 'disbursement_id': None,
                        'prisoner_profile': None, 'recipient_profile': None,
                        'sender_profile': {
                            'id': 2, 'debit_card_details': [{'cardholder_names': ['Fred Smith']}],
                        },
                    },
                ]},
            )
            response = self.client.get(reverse('security:notification_list'))
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('Page 1 of 1.', response_content)
        self.assertEqual(response_content.count('Mary Halls'), 1)
        self.assertEqual(response_content.count('Fred Smith'), 1)
        self.assertEqual(response_content.count('JAMES HALLS'), 1)
        self.assertEqual(response_content.count('JILLY HALL'), 1)
        self.assertEqual(response_content.count('1 transaction'), 2)
        self.assertEqual(response_content.count('2 transactions'), 2)
