import logging
from unittest import mock

from django.core.urlresolvers import reverse
from django.test import SimpleTestCase
from mtp_common.auth.test_utils import generate_tokens
from mtp_common.test_utils import silence_logger

from security import required_permissions


class SecurityBaseTestCase(SimpleTestCase):
    @mock.patch('mtp_common.auth.backends.api_client')
    def login(self, mock_api_client):
        mock_api_client.authenticate.return_value = {
            'pk': 5,
            'token': generate_tokens(),
            'user_data': {
                'first_name': 'Sam',
                'last_name': 'Hall',
                'username': 'shall',
                'applications': ['noms-ops'],
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
    def test_can_access_security_dashboard(self):
        response = self.login()
        self.assertContains(response, '<!-- dashboard -->')

    def test_cannot_access_prisoner_location_admin(self):
        self.login()
        response = self.client.get(reverse('location_file_upload'), follow=True)
        self.assertNotContains(response, '<!-- location_file_upload -->')
        self.assertContains(response, '<!-- dashboard -->')


class SecurityViewTestCase(SecurityBaseTestCase):
    view_name = None

    def setUp(self):
        self.mocked_prison_data = mock.patch('security.forms.get_prison_details_choices', return_value={
            'prisons': [('IXB', 'Prison 1'), ('INP', 'Prison 2')],
            'regions': [('London', 'London'), ('West Midlands', 'West Midlands')],
            'populations': [('male', 'Male'), ('female', 'Female'), ('adults', 'Adults')],
            'categories': [('A', 'Category A'), ('B', 'Category B')],
        })
        self.mocked_prison_data.start()

    def tearDown(self):
        self.mocked_prison_data.stop()

    def test_can_access_security_view(self):
        if not self.view_name:
            return
        self.login()
        response = self.client.get(reverse(self.view_name), follow=True)
        self.assertContains(response, '<!-- %s -->' % self.view_name)


class SenderListTestCase(SecurityViewTestCase):
    view_name = 'security:sender_grouped'

    @mock.patch('security.forms.get_connection')
    def test_displays_results(self, mocked_connection):
        response_data = {
            'count': 1,
            'previous': None,
            'next': 'http://mtp.local/credits/senders/?limit=20&offset=20&ordering=-prisoner_count',
            'results': [
                {
                    'sender_name': 'MAISIE NOLAN',
                    'sender_sort_code': '101010',
                    'sender_account_number': '12312345',
                    'sender_roll_number': '',
                    'prisoner_count': 3,
                    'credit_count': 4,
                    'credit_total': 41000,
                    'prisoners': [
                        {
                            'prisoner_number': 'A1450AE',
                            'prisoner_name': 'NICHOLAS FINNEY',
                            'prison_name': 'Prison 1',
                            'credit_count': 1,
                            'credit_total': 10000,
                        },
                        {
                            'prisoner_number': 'A1409AE',
                            'prisoner_name': 'JAMES HALLS',
                            'prison_name': 'Prison 1',
                            'credit_count': 2,
                            'credit_total': 26000,
                        },
                        {
                            'prisoner_number': 'A1421AE',
                            'prisoner_name': 'JAMES HERBERT',
                            'prison_name': 'Prison 1',
                            'credit_count': 1,
                            'credit_total': 5000,
                        },
                        {
                            # NB: this is not counted in group sums
                            'prisoner_number': None,
                            'prisoner_name': None,
                            'prison_name': None,
                            'credit_count': 1,
                            'credit_total': 1700,
                        },
                    ]
                },
            ]
        }
        mocked_connection().credits.senders.get.return_value = response_data

        self.login()
        response = self.client.post(reverse(self.view_name), {'page': '1'})
        self.assertContains(response, 'MAISIE NOLAN')
        response_content = response.content.decode(response.charset)
        self.assertIn('410.00', response_content)
        self.assertIn('Cannot be credited', response_content)
        for prisoner in response_data['results'][0]['prisoners']:
            if not prisoner['prisoner_number']:
                continue
            self.assertIn(prisoner['prisoner_number'], response_content)
            self.assertIn(prisoner['prisoner_name'], response_content)


class PrisonerListTestCase(SecurityViewTestCase):
    view_name = 'security:prisoner_grouped'

    @mock.patch('security.forms.get_connection')
    def test_displays_results(self, mocked_connection):
        response_data = {
            'count': 1,
            'previous': None,
            'next': 'http://localhost:8000/credits/prisoners/?limit=20&offset=20&ordering=-prisoner_count',
            'results': [
                {
                    'prisoner_number': 'A1409AE',
                    'prisoner_name': 'JAMES HALLS',
                    'prison_name': 'Prison 1',
                    'sender_count': 2,
                    'credit_count': 3,
                    'credit_total': 31000,
                    'senders': [
                        {
                            'sender_name': 'ANJELICA HALLS',
                            'sender_sort_code': '',
                            'sender_account_number': '',
                            'sender_roll_number': '',
                            'credit_count': 1,
                            'credit_total': 5000,
                        },
                        {
                            'sender_name': 'MAISIE NOLAN',
                            'sender_sort_code': '101010',
                            'sender_account_number': '12312345',
                            'sender_roll_number': '',
                            'credit_count': 2,
                            'credit_total': 26000,
                        },
                    ],
                }
            ]
        }
        mocked_connection().credits.prisoners.get.return_value = response_data

        self.login()
        response = self.client.post(reverse(self.view_name), {'page': '1'})
        self.assertContains(response, 'JAMES HALLS')
        response_content = response.content.decode(response.charset)
        self.assertIn('A1409AE', response_content)
        self.assertIn('310.00', response_content)
        for sender in response_data['results'][0]['senders']:
            self.assertIn(sender['sender_name'], response_content)
            if sender['sender_account_number']:
                self.assertIn(sender['sender_account_number'], response_content)


class CreditsListTestCase(SecurityViewTestCase):
    view_name = 'security:credits'

    @mock.patch('security.forms.get_connection')
    def test_displays_results(self, mocked_connection):
        response_data = {
            'count': 2,
            'previous': None,
            'next': 'http://localhost:8000/credits/?limit=20&offset=20&ordering=-amount',
            'results': [
                {
                    'id': 1,
                    'source': 'online',
                    'amount': 23000,
                    'intended_recipient': 'GEORGE MELLEY',
                    'prisoner_number': 'A1411AE', 'prisoner_name': 'GEORGE MELLEY',
                    'prison': 'LEI', 'prison_name': 'HMP LEEDS',
                    'sender_name': None,
                    'sender_sort_code': None, 'sender_account_number': None, 'sender_roll_number': None,
                    'resolution': 'credited',
                    'owner': None, 'owner_name': None,
                    'received_at': '2016-05-25T20:24:00Z', 'credited_at': '2016-05-25T20:27:00Z', 'refunded_at': None,
                },
                {
                    'id': 2,
                    'source': 'bank_transfer',
                    'amount': 27500,
                    'intended_recipient': None,
                    'prisoner_number': 'A1413AE', 'prisoner_name': 'NORMAN STANLEY FLETCHER',
                    'prison': 'LEI', 'prison_name': 'HMP LEEDS',
                    'sender_name': 'HEIDENREICH X',
                    'sender_sort_code': '219657', 'sender_account_number': '88447894', 'sender_roll_number': '',
                    'resolution': 'credited',
                    'owner': None, 'owner_name': None,
                    'received_at': '2016-05-22T23:00:00Z', 'credited_at': '2016-05-23T01:10:00Z', 'refunded_at': None,
                },
            ]
        }
        mocked_connection().credits.get.return_value = response_data

        self.login()
        response = self.client.post(reverse(self.view_name), {'page': '1', 'ordering': '-amount'})
        self.assertContains(response, 'GEORGE MELLEY')
        response_content = response.content.decode(response.charset)
        self.assertIn('A1413AE', response_content)
        self.assertIn('275.00', response_content)
        self.assertIn('Bank transfer', response_content)
        self.assertIn('Debit card', response_content)


class CreditsExportTestCase(SecurityBaseTestCase):

    @mock.patch('security.forms.get_connection')
    def test_creates_csv(self, mocked_connection):
        response_data = {
            'count': 2,
            'previous': None,
            'next': None,
            'results': [
                {
                    'id': 1,
                    'source': 'online',
                    'amount': 23000,
                    'intended_recipient': 'GEORGE MELLEY',
                    'prisoner_number': 'A1411AE', 'prisoner_name': 'GEORGE MELLEY',
                    'prison': 'LEI', 'prison_name': 'HMP LEEDS',
                    'sender_name': None,
                    'sender_sort_code': None, 'sender_account_number': None, 'sender_roll_number': None,
                    'resolution': 'credited',
                    'owner': None, 'owner_name': None,
                    'received_at': '2016-05-25T20:24:00Z', 'credited_at': '2016-05-25T20:27:00Z', 'refunded_at': None,
                },
                {
                    'id': 2,
                    'source': 'bank_transfer',
                    'amount': 27500,
                    'intended_recipient': None,
                    'prisoner_number': 'A1413AE', 'prisoner_name': 'NORMAN STANLEY FLETCHER',
                    'prison': 'LEI', 'prison_name': 'HMP LEEDS',
                    'sender_name': 'HEIDENREICH X',
                    'sender_sort_code': '219657', 'sender_account_number': '88447894', 'sender_roll_number': '',
                    'resolution': 'credited',
                    'owner': None, 'owner_name': None,
                    'received_at': '2016-05-22T23:00:00Z', 'credited_at': '2016-05-23T01:10:00Z', 'refunded_at': None,
                },
            ]
        }
        mocked_connection().credits.get.return_value = response_data

        expected_result = (
            'prisoner_name,prisoner_number,prison,sender_name,' +
            'sender_sort_code,sender_account_number,sender_roll_number,' +
            'amount,resolution,received_at\r\n' +
            'GEORGE MELLEY,A1411AE,LEI,,,,,230.00,credited,2016-05-25T20:24:00Z\r\n' +
            'NORMAN STANLEY FLETCHER,A1413AE,LEI,HEIDENREICH X,219657,88447894,,' +
            '275.00,credited,2016-05-22T23:00:00Z\r\n'
        )

        self.login()
        response = self.client.get(
            reverse('security:credits_export') + '?page=1'
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual('text/csv', response['Content-Type'])
        self.assertEqual(
            bytes(expected_result, 'utf8'),
            response.content
        )

    @mock.patch('security.forms.get_connection')
    def test_no_data(self, mocked_connection):
        response_data = {
            'count': 0,
            'previous': None,
            'next': None,
            'results': []
        }
        mocked_connection().credits.get.return_value = response_data

        expected_result = (
            'prisoner_name,prisoner_number,prison,sender_name,' +
            'sender_sort_code,sender_account_number,sender_roll_number,' +
            'amount,resolution,received_at\r\n'
        )

        self.login()
        response = self.client.get(
            reverse('security:credits_export') + '?page=1'
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual('text/csv', response['Content-Type'])
        self.assertEqual(
            bytes(expected_result, 'utf8'),
            response.content
        )

    @mock.patch('security.forms.get_connection')
    def test_missing_page_redirects_to_form(self, mocked_connection):
        self.login()
        response = self.client.get(
            reverse('security:credits_export') + '?prison=LEI'
        )
        self.assertRedirects(response, reverse('security:credits') + '?prison=LEI')

    @mock.patch('security.forms.get_connection')
    def test_invalid_params_redirects_to_form(self, mocked_connection):
        self.login()
        response = self.client.get(
            reverse('security:credits_export') + '?page=1&received_at__gte=LL'
        )
        self.assertRedirects(response, reverse('security:credits'))
