import datetime

from django.core.urlresolvers import reverse
from django.http import QueryDict
from django.utils.timezone import make_aware
import responses

from security import (
    hmpps_employee_flag,
    confirmed_prisons_flag,
    notifications_pilot_flag,
)
from security.tests.utils import api_url
from security.tests.views.test_base import SecurityBaseTestCase


class NotificationsTestCase(SecurityBaseTestCase):
    def test_cannot_access_without_pilot_flag(self):
        with responses.RequestsMock() as rsps:
            self.login(follow=False, rsps=rsps)
            response = self.client.get(reverse('security:notification_list'), follow=True)
        self.assertNotContains(response, '<!-- security:notification_list -->')

    def login_with_pilot_user(self, rsps):
        self.login(user_data=self.get_user_data(flags=[
            notifications_pilot_flag, hmpps_employee_flag, confirmed_prisons_flag,
        ]), rsps=rsps)

    def test_no_notifications_not_monitoring(self):
        """
        Expect to see a message if you're not monitoring anything and have no notifications
        """
        with responses.RequestsMock() as rsps:
            self.login_with_pilot_user(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + '?rule=MONP&rule=MONS&offset=0&limit=25',
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
            self.login_with_pilot_user(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + '?rule=MONP&rule=MONS&offset=0&limit=25',
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
            self.login_with_pilot_user(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + '?rule=MONP&rule=MONS&offset=0&limit=25',
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
            self.login_with_pilot_user(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + '?rule=MONP&rule=MONS&offset=0&limit=25',
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
            self.login_with_pilot_user(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + '?rule=MONP&rule=MONS&offset=0&limit=25',
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
                            make_aware(datetime.datetime(2019, 7, 15, 10) - datetime.timedelta(days)).isoformat()
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
            self.login_with_pilot_user(rsps)
            rsps.add(
                rsps.GET,
                api_url('/events/pages/') + '?rule=MONP&rule=MONS&offset=0&limit=25',
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
