import base64
from contextlib import contextmanager
import json
import logging
import tempfile
from unittest import mock

from django.core import mail
from django.core.urlresolvers import reverse
from django.test import SimpleTestCase, override_settings
from mtp_common.auth import USER_DATA_SESSION_KEY
from mtp_common.auth.test_utils import generate_tokens
from mtp_common.test_utils import silence_logger
from openpyxl import load_workbook
import responses

from security import required_permissions, hmpps_employee_flag, not_hmpps_employee_flag
from security.tests import api_url, nomis_url, TEST_IMAGE_DATA


override_nomis_settings = override_settings(
    NOMIS_API_BASE_URL='https://nomis.local/',
    NOMIS_API_CLIENT_TOKEN='hello',
    NOMIS_API_PRIVATE_KEY=(
        '-----BEGIN EC PRIVATE KEY-----\n'
        'MHcCAQEEIOhhs3RXk8dU/YQE3j2s6u97mNxAM9s+13S+cF9YVgluoAoGCCqGSM49\n'
        'AwEHoUQDQgAE6l49nl7NN6k6lJBfGPf4QMeHNuER/o+fLlt8mCR5P7LXBfMG6Uj6\n'
        'TUeoge9H2N/cCafyhCKdFRdQF9lYB2jB+A==\n'
        '-----END EC PRIVATE KEY-----\n'
    ),  # this key is just for tests, doesn't do anything
)

sample_prisons = [
    {
        'nomis_id': 'AAI',
        'general_ledger_code': '001',
        'name': 'HMP & YOI Test 1', 'short_name': 'Test 1',
        'region': 'London',
        'categories': [{'description': 'Category D', 'name': 'D'},
                       {'description': 'Young Offender Institution', 'name': 'YOI'}],
        'populations': [{'description': 'Female', 'name': 'female'},
                        {'description': 'Male', 'name': 'male'},
                        {'description': 'Young offenders', 'name': 'young'}],
        'pre_approval_required': False,
    },
    {
        'nomis_id': 'BBI',
        'general_ledger_code': '002',
        'name': 'HMP Test 2', 'short_name': 'Test 2',
        'region': 'London',
        'categories': [{'description': 'Category D', 'name': 'D'}],
        'populations': [{'description': 'Male', 'name': 'male'}],
        'pre_approval_required': False,
    },
]
default_user_prisons = (sample_prisons[1],)


def sample_prison_list():
    responses.add(
        responses.GET,
        api_url('/prisons/'),
        json={
            'count': len(sample_prisons),
            'results': sample_prisons,
        }
    )


def no_saved_searches():
    responses.add(
        responses.GET,
        api_url('/searches/'),
        json={
            'count': 0,
            'results': []
        },
    )


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
    DISBURSEMENT_PRISONS=['AAI', 'BBI']
)
class SecurityBaseTestCase(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.notifications_mock = mock.patch('mtp_common.templatetags.mtp_common.notifications_for_request',
                                             return_value=[])
        self.notifications_mock.start()

    def tearDown(self):
        self.notifications_mock.stop()
        super().tearDown()

    @mock.patch('mtp_common.auth.backends.api_client')
    def login(self, mock_api_client, follow=True, flags=(hmpps_employee_flag,)):
        no_saved_searches()
        return self._login(mock_api_client, follow=follow, flags=flags)

    @mock.patch('mtp_common.auth.backends.api_client')
    def login_test_searches(self, mock_api_client, follow=True):
        return self._login(mock_api_client, follow=follow)

    def _login(self, mock_api_client, follow=True, prisons=default_user_prisons, flags=(hmpps_employee_flag,)):
        mock_api_client.authenticate.return_value = {
            'pk': 5,
            'token': generate_tokens(),
            'user_data': {
                'first_name': 'Sam',
                'last_name': 'Hall',
                'username': 'shall',
                'email': 'sam@mtp.local',
                'permissions': required_permissions,
                'prisons': prisons,
                'flags': flags,
            }
        }

        response = self.client.post(
            reverse('login'),
            data={'username': 'shall', 'password': 'pass'},
            follow=follow
        )
        if follow:
            self.assertEqual(response.status_code, 200)
        else:
            self.assertEqual(response.status_code, 302)
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
    @responses.activate
    def test_can_access_security_dashboard(self):
        response = self.login()
        self.assertContains(response, '<!-- dashboard -->')

    @responses.activate
    def test_cannot_access_prisoner_location_admin(self):
        self.login()
        no_saved_searches()
        response = self.client.get(reverse('location_file_upload'), follow=True)
        self.assertNotContains(response, '<!-- location_file_upload -->')
        self.assertContains(response, '<!-- dashboard -->')


class HMPPSEmployeeTestCase(SecurityBaseTestCase):
    protected_views = ['dashboard', 'security:credit_list', 'security:sender_list', 'security:prisoner_list']

    @responses.activate
    def test_redirects_when_no_flag(self):
        self.login(flags=[])
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- security:hmpps_employee -->')

    @responses.activate
    def test_non_employee_flag_disallows_entry(self):
        self.login(flags=[not_hmpps_employee_flag])
        for view in self.protected_views:
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- security:not_hmpps_employee -->')
            self.assertIn('You can’t use this tool', response.content.decode())

    @responses.activate
    def test_employee_can_access(self):
        self.login(flags=[hmpps_employee_flag])

        def assertViewAccessible(view):  # noqa: N802
            response = self.client.get(reverse(view), follow=True)
            self.assertContains(response, '<!-- %s -->' % view)

        assertViewAccessible('dashboard')
        sample_prison_list()
        assertViewAccessible('security:credit_list')

    @responses.activate
    def test_employee_flag_set(self):
        self.login(flags=['abc'])
        responses.add(
            responses.PUT,
            api_url('/users/shall/flags/%s/' % hmpps_employee_flag),
            json={}
        )
        response = self.client.post(reverse('security:hmpps_employee'), data={
            'confirmation': 'yes',
        }, follow=True)
        self.assertContains(response, '<!-- dashboard -->')
        self.assertIn(hmpps_employee_flag, self.client.session[USER_DATA_SESSION_KEY]['flags'])
        self.assertIn(hmpps_employee_flag, response.context['user'].user_data['flags'])

    @responses.activate
    def test_redirects_to_referrer(self):
        self.login(flags=[])
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
        self.login(flags=['123'])
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


class SecurityViewTestCase(SecurityBaseTestCase):
    view_name = None
    api_list_path = None
    bank_transfer_sender = {
        'id': 9,
        'credit_count': 4,
        'credit_total': 41000,
        'prisoner_count': 3,
        'prison_count': 2,
        'bank_transfer_details': [
            {
                'sender_name': 'MAISIE NOLAN',
                'sender_sort_code': '101010',
                'sender_account_number': '12312345',
                'sender_roll_number': '',
            }
        ],
        'created': '2016-05-25T20:24:00Z',
        'modified': '2016-05-25T20:24:00Z',
    }
    debit_card_sender = {
        'id': 9,
        'credit_count': 4,
        'credit_total': 42000,
        'prisoner_count': 3,
        'prison_count': 2,
        'bank_transfer_details': [],
        'debit_card_details': [
            {
                'card_number_last_digits': '1234',
                'card_expiry_date': '10/20',
                'postcode': 'SW137NJ',
                'sender_emails': ['m@outside.local', 'M@OUTSIDE.LOCAL', 'mn@outside.local'],
                'cardholder_names': ['Maisie N', 'MAISIE N', 'Maisie Nolan'],
            }
        ],
        'created': '2016-05-25T20:24:00Z',
        'modified': '2016-05-25T20:24:00Z',
    }
    prisoner_profile = {
        'id': 8,
        'credit_count': 3,
        'credit_total': 31000,
        'sender_count': 2,
        'prisoner_name': 'JAMES HALLS',
        'prisoner_number': 'A1409AE',
        'prisoner_dob': '1986-12-09',
        'current_prison': {'nomis_id': 'PRN', 'name': 'Prison'},
        'prisons': [{'nomis_id': 'PRN', 'name': 'Prison'}],
        'provided_names': ['Jim Halls', 'JAMES HALLS', 'James Halls '],
        'created': '2016-05-25T20:24:00Z',
        'modified': '2016-05-25T20:24:00Z',
    }
    credit_object = {
        'id': 1,
        'amount': 10250,
        'resolution': 'credited', 'anonymous': False,
        'credited_at': '2016-05-25T20:24:00Z',
        'owner': 1, 'owner_name': 'Clerk',
        'prison': 'PRN', 'prison_name': 'Prison', 'prisoner_name': 'JAMES HALLS', 'prisoner_number': 'A1409AE',
        'reconciliation_code': None,
        'received_at': '2017-01-25T12:00:00Z',
        'refunded_at': None,
        'reviewed': False, 'comments': [],
        'source': 'bank_transfer',
        'sender_sort_code': '101010', 'sender_account_number': '12312345', 'sender_roll_number': '',
        'card_expiry_date': None, 'card_number_last_digits': None,
        'sender_name': 'MAISIE NOLAN',
        'sender_email': None,
        'intended_recipient': None,
    }

    @responses.activate
    @mock.patch('security.forms.object_base.SecurityForm.get_object_list')
    def test_can_access_security_view(self, mocked_form_method):
        mocked_form_method.return_value = []
        if not self.view_name:
            return
        sample_prison_list()
        self.login()
        response = self.client.get(reverse(self.view_name), follow=True)
        self.assertContains(response, '<!-- %s -->' % self.view_name)

    @responses.activate
    def test_filtering_by_one_prison(self):
        if not self.api_list_path:
            return
        self.login()
        no_saved_searches()
        sample_prison_list()
        responses.add(responses.GET, api_url(self.api_list_path), json={'count': 0, 'results': []})
        response = self.client.get(reverse(self.view_name) + '?page=1&prison=BBI', follow=False)
        self.assertContains(response, 'HMP Test 2')
        calls = list(filter(lambda call: self.api_list_path in call.request.url, responses.calls))
        self.assertEqual(len(calls), 1)
        self.assertIn('prison=BBI', calls[0].request.url)

    @responses.activate
    def test_filtering_by_many_prisons(self):
        if not self.api_list_path:
            return
        self.login()
        no_saved_searches()
        sample_prison_list()
        responses.add(responses.GET, api_url(self.api_list_path), json={'count': 0, 'results': []})
        response = self.client.get(reverse(self.view_name) + '?page=1&prison=BBI&prison=AAI', follow=False)
        self.assertContains(response, 'HMP &amp; YOI Test 1')
        self.assertContains(response, 'HMP Test 2')
        calls = list(filter(lambda call: self.api_list_path in call.request.url, responses.calls))
        self.assertEqual(len(calls), 1)
        self.assertIn('prison=AAI&prison=BBI', calls[0].request.url)

    @responses.activate
    def test_filtering_by_many_prisons_alternate(self):
        if not self.api_list_path:
            return
        self.login()
        no_saved_searches()
        sample_prison_list()
        responses.add(responses.GET, api_url(self.api_list_path), json={'count': 0, 'results': []})
        response = self.client.get(reverse(self.view_name) + '?page=1&prison=BBI,AAI', follow=False)
        self.assertContains(response, 'HMP &amp; YOI Test 1')
        self.assertContains(response, 'HMP Test 2')
        calls = list(filter(lambda call: self.api_list_path in call.request.url, responses.calls))
        self.assertEqual(len(calls), 1)
        self.assertIn('prison=AAI&prison=BBI', calls[0].request.url)


class SenderListTestCase(SecurityViewTestCase):
    view_name = 'security:sender_list'
    detail_view_name = 'security:sender_detail'
    api_list_path = '/senders/'

    @responses.activate
    def test_displays_results(self):
        self.login()
        no_saved_searches()
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url(self.api_list_path),
            json={
                'count': 2,
                'results': [self.bank_transfer_sender, self.debit_card_sender],
            }
        )
        response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'MAISIE NOLAN')
        response_content = response.content.decode(response.charset)
        self.assertIn('£410.00', response_content)
        self.assertIn('£420.00', response_content)

    @responses.activate
    def test_displays_bank_transfer_detail(self):
        self.login()
        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/senders/{id}/'.format(id=9)),
            json=self.bank_transfer_sender
        )
        responses.add(
            responses.GET,
            api_url('/senders/{id}/credits/'.format(id=9)),
            json={
                'count': 4,
                'results': [self.credit_object, self.credit_object, self.credit_object, self.credit_object],
            }
        )

        response = self.client.get(reverse(self.detail_view_name, kwargs={'sender_id': 9}))
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('MAISIE', response_content)
        self.assertIn('12312345', response_content)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('£102.50', response_content)

    @responses.activate
    def test_displays_debit_card_detail(self):
        self.login()
        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/senders/{id}/'.format(id=9)),
            json=self.debit_card_sender
        )
        responses.add(
            responses.GET,
            api_url('/senders/{id}/credits/'.format(id=9)),
            json={
                'count': 4,
                'results': [self.credit_object, self.credit_object, self.credit_object, self.credit_object],
            }
        )
        response = self.client.get(reverse(self.detail_view_name, kwargs={'sender_id': 9}))
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('**** **** **** 1234', response_content)
        self.assertIn('10/20', response_content)
        self.assertIn('SW137NJ', response_content)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('£102.50', response_content)

    @responses.activate
    def test_detail_not_found(self):
        self.login()
        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/senders/{id}/'.format(id=9)),
            status=404
        )
        responses.add(
            responses.GET,
            api_url('/senders/{id}/credits/'.format(id=9)),
            status=404
        )
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'sender_id': 9}))
        self.assertEqual(response.status_code, 404)

    @responses.activate
    def test_connection_errors(self):
        self.login()
        no_saved_searches()
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/senders/{id}/'.format(id=9)),
            status=500
        )
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'non-field-error')

        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/senders/{id}/'.format(id=9)),
            status=500
        )
        responses.add(
            responses.GET,
            api_url('/senders/{id}/credits/'.format(id=9)),
            status=500
        )
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'sender_id': 9}))
        self.assertContains(response, 'non-field-error')


class PrisonerListTestCase(SecurityViewTestCase):
    view_name = 'security:prisoner_list'
    detail_view_name = 'security:prisoner_detail'
    api_list_path = '/prisoners/'

    @responses.activate
    def test_displays_results(self):
        self.login()
        no_saved_searches()
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url(self.api_list_path),
            json={
                'count': 1,
                'results': [self.prisoner_profile],
            }
        )
        response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'JAMES HALLS')
        response_content = response.content.decode(response.charset)
        self.assertIn('A1409AE', response_content)
        self.assertIn('310.00', response_content)

    @responses.activate
    @override_nomis_settings
    def test_displays_detail(self):
        self.login()
        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/'.format(id=9)),
            json=self.prisoner_profile
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/credits/'.format(id=9)),
            json={
                'count': 4,
                'results': [self.credit_object, self.credit_object, self.credit_object, self.credit_object],
            }
        )

        response = self.client.get(reverse(
            self.detail_view_name, kwargs={'prisoner_id': 9}))
        self.assertContains(response, 'JAMES HALLS')
        response_content = response.content.decode(response.charset)
        self.assertIn('Jim Halls', response_content)
        self.assertNotIn('James Halls', response_content)
        self.assertIn('MAISIE', response_content)
        self.assertIn('£102.50', response_content)

    @responses.activate
    def test_detail_not_found(self):
        self.login()
        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/'.format(id=9)),
            status=404
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/credits/'.format(id=9)),
            status=404
        )
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'prisoner_id': 9}))
        self.assertEqual(response.status_code, 404)

    @responses.activate
    def test_connection_errors(self):
        self.login()
        no_saved_searches()
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/'.format(id=9)),
            status=500
        )
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'non-field-error')

        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/'.format(id=9)),
            status=500
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/credits/'.format(id=9)),
            status=500
        )
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'prisoner_id': 9}))
        self.assertContains(response, 'non-field-error')


class CreditsListTestCase(SecurityViewTestCase):
    view_name = 'security:credit_list'
    detail_view_name = 'security:credit_detail'
    api_list_path = '/credits/'

    debit_card_credit = {
        'id': 1,
        'source': 'online',
        'amount': 23000,
        'intended_recipient': 'Mr G Melley',
        'prisoner_number': 'A1411AE', 'prisoner_name': 'GEORGE MELLEY',
        'prison': 'LEI', 'prison_name': 'HMP LEEDS',
        'sender_name': None,
        'sender_sort_code': None, 'sender_account_number': None,
        'sender_roll_number': None,
        'card_number_last_digits': '4444', 'card_expiry_date': '07/18',
        'resolution': 'credited',
        'owner': None, 'owner_name': 'Maria',
        'received_at': '2016-05-25T20:24:00Z',
        'credited_at': '2016-05-25T20:27:00Z', 'refunded_at': None,
        'comments': [{'user_full_name': 'Eve', 'comment': 'OK'}],
    }
    bank_transfer_credit = {
        'id': 2,
        'source': 'bank_transfer',
        'amount': 27500,
        'intended_recipient': None,
        'prisoner_number': 'A1413AE', 'prisoner_name': 'NORMAN STANLEY FLETCHER',
        'prison': 'LEI', 'prison_name': 'HMP LEEDS',
        'sender_name': 'HEIDENREICH X',
        'sender_sort_code': '219657', 'sender_account_number': '88447894',
        'sender_roll_number': '', 'resolution': 'credited',
        'owner': None, 'owner_name': 'Maria',
        'received_at': '2016-05-22T23:00:00Z',
        'credited_at': '2016-05-23T01:10:00Z', 'refunded_at': None,
        'comments': [],
    }

    @responses.activate
    def test_displays_results(self):
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url(self.api_list_path),
            json={
                'count': 2,
                'previous': None,
                'next': 'http://localhost:8000/credits/?limit=20&offset=20&ordering=-amount',
                'results': [
                    self.debit_card_credit,
                    self.bank_transfer_credit,
                ]
            }
        )

        self.login()
        response = self.client.get(reverse(self.view_name), {'ordering': '-amount'})
        self.assertContains(response, 'GEORGE MELLEY')
        response_content = response.content.decode(response.charset)
        self.assertIn('A1413AE', response_content)
        self.assertIn('275.00', response_content)
        self.assertIn('Bank transfer', response_content)
        self.assertIn('Debit card', response_content)

    @responses.activate
    def test_debit_card_detail(self):
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/credits/'),
            json={
                'count': 1, 'previous': None, 'next': None,
                'results': [self.debit_card_credit]
            }
        )

        self.login()
        response = self.client.get(reverse(self.detail_view_name, kwargs={'credit_id': '1'}))
        self.assertContains(response, 'Debit card')
        response_content = response.content.decode(response.charset)
        self.assertIn('£230.00', response_content)
        self.assertIn('GEORGE MELLEY', response_content)
        self.assertIn('Mr G Melley', response_content)
        self.assertIn('A1411AE', response_content)
        self.assertIn('Credited by Maria', response_content)
        self.assertIn('Eve', response_content)
        self.assertIn('OK', response_content)

    @responses.activate
    def test_bank_transfer_detail(self):
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/credits/'),
            json={
                'count': 1, 'previous': None, 'next': None,
                'results': [self.bank_transfer_credit]
            }
        )

        self.login()
        response = self.client.get(reverse(self.detail_view_name, kwargs={'credit_id': '2'}))
        self.assertContains(response, 'Bank transfer')
        response_content = response.content.decode(response.charset)
        self.assertIn('£275.00', response_content)
        self.assertIn('NORMAN STANLEY FLETCHER', response_content)
        self.assertIn('21-96-57', response_content)
        self.assertIn('88447894', response_content)
        self.assertIn('Credited by Maria', response_content)


class DisbursementsListTestCase(SecurityViewTestCase):
    view_name = 'security:disbursement_list'
    detail_view_name = 'security:disbursement_detail'
    api_list_path = '/disbursements/'

    bank_transfer_disbursement = {
        'id': 99,
        'created': '2018-02-12T12:00:00Z', 'modified': '2018-02-12T12:00:00Z',
        'method': 'bank_transfer',
        'amount': 2000,
        'resolution': 'sent',
        'nomis_transaction_id': '1234567-1', 'invoice_number': '1000099',
        'prisoner_number': 'A1409AE', 'prisoner_name': 'JAMES HALLS',
        'prison': 'ABC', 'prison_name': 'HMP Test1',
        'recipient_first_name': 'Jack', 'recipient_last_name': 'Halls',
        'recipient_email': '', 'remittance_description': '',
        'address_line1': '102 Petty France', 'address_line2': '',
        'city': 'London', 'postcode': 'SW1H 9AJ', 'country': None,
        'account_number': '1234567', 'sort_code': '112233', 'roll_number': None,
        'comments': [],
        'log_set': [{'action': 'created',
                     'created': '2018-02-12T12:00:00Z',
                     'user': {'first_name': 'Mary', 'last_name': 'Smith', 'username': 'msmith'}},
                    {'action': 'confirmed',
                     'created': '2018-02-12T12:00:00Z',
                     'user': {'first_name': 'John', 'last_name': 'Smith', 'username': 'jsmith'}},
                    {'action': 'sent',
                     'created': '2018-02-12T12:00:00Z',
                     'user': {'first_name': 'SSCL', 'last_name': '', 'username': 'sscl'}}],
    }
    cheque_disbursement = {
        'id': 100,
        'created': '2018-02-10T10:00:00Z', 'modified': '2018-02-10T12:00:00Z',
        'method': 'cheque',
        'amount': 1000,
        'resolution': 'confirmed',
        'nomis_transaction_id': '1234568-1', '': 'PMD1000100',
        'prisoner_number': 'A1401AE', 'prisoner_name': 'JILLY HALL',
        'prison': 'DEF', 'prison_name': 'HMP Test2',
        'recipient_first_name': 'Jilly', 'recipient_last_name': 'Halls',
        'recipient_email': 'jilly@mtp.local', 'remittance_description': 'PRESENT',
        'address_line1': '102 Petty France', 'address_line2': '',
        'city': 'London', 'postcode': 'SW1H 9AJ', 'country': None,
        'account_number': '', 'sort_code': '', 'roll_number': None,
        'comments': [],
        'log_set': [{'action': 'created',
                     'created': '2018-02-10T10:00:00Z',
                     'user': {'first_name': 'Mary', 'last_name': 'Smith', 'username': 'msmith'}},
                    {'action': 'confirmed',
                     'created': '2018-02-10T11:00:00Z',
                     'user': {'first_name': 'John', 'last_name': 'Smith', 'username': 'jsmith'}}]
    }

    @responses.activate
    def test_displays_results(self):
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url(self.api_list_path),
            json={
                'count': 2,
                'previous': None,
                'next': 'http://localhost:8000/disbursements/?limit=20&offset=20&ordering=-amount',
                'results': [
                    self.bank_transfer_disbursement,
                    self.cheque_disbursement,
                ]
            }
        )

        self.login()
        response = self.client.get(reverse(self.view_name), {'ordering': '-amount'})
        self.assertContains(response, 'JAMES HALLS')
        response_content = response.content.decode(response.charset)
        self.assertIn('A1409AE', response_content)
        self.assertIn('£20.00', response_content)
        self.assertIn('by bank transfer', response_content)
        self.assertIn('Sent', response_content)
        self.assertIn('A1401AE', response_content)
        self.assertIn('£10.00', response_content)
        self.assertIn('by cheque', response_content)
        self.assertIn('Confirmed', response_content)

    @responses.activate
    def test_bank_transfer_detail(self):
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/disbursements/99/'),
            json=self.bank_transfer_disbursement
        )

        self.login()
        response = self.client.get(reverse(self.detail_view_name, kwargs={'disbursement_id': '99'}))
        self.assertContains(response, 'Bank transfer')
        response_content = response.content.decode(response.charset)
        self.assertIn('£20.00', response_content)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('Jack Halls', response_content)
        self.assertIn('1234567-1', response_content)
        self.assertIn('1000099', response_content)
        self.assertIn('Confirmed by John Smith', response_content)
        self.assertIn('None given', response_content)

    @responses.activate
    def test_cheque_detail(self):
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/disbursements/100/'),
            json=self.cheque_disbursement
        )

        self.login()
        response = self.client.get(reverse(self.detail_view_name, kwargs={'disbursement_id': '100'}))
        self.assertContains(response, 'Cheque')
        response_content = response.content.decode(response.charset)
        self.assertIn('£10.00', response_content)
        self.assertIn('JILLY HALL', response_content)
        self.assertIn('Jilly Halls', response_content)
        self.assertIn('1234568-1', response_content)
        self.assertNotIn('PMD1000100', response_content)
        self.assertIn('Confirmed by John Smith', response_content)
        self.assertIn('jilly@mtp.local', response_content)
        self.assertIn('PRESENT', response_content)


@contextmanager
def temp_spreadsheet(data):
    with tempfile.TemporaryFile() as f:
        f.write(data)
        wb = load_workbook(f)
        ws = wb.active
        yield ws


class CreditsExportTestCase(SecurityBaseTestCase):
    expected_headers = [
        'Prisoner name', 'Prisoner number', 'Prison', 'Sender name', 'Payment method',
        'Bank transfer sort code', 'Bank transfer account', 'Bank transfer roll number',
        'Debit card number', 'Debit card expiry', 'Address', 'Amount', 'Date received',
        'Credited status', 'Date credited', 'NOMIS ID', 'IP'
    ]

    @responses.activate
    def test_creates_xslx(self):
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
                    'card_number_last_digits': None, 'card_expiry_date': None,
                    'billing_address': {'line1': '102PF', 'city': 'London'},
                    'ip_address': '127.0.0.1', 'sender_email': 'ian@mail.local',
                    'resolution': 'credited', 'nomis_transaction_id': None,
                    'owner': None, 'owner_name': None,
                    'received_at': '2016-05-25T20:24:00Z',
                    'credited_at': '2016-05-25T20:27:00Z', 'refunded_at': None,
                },
                {
                    'id': 2,
                    'source': 'bank_transfer',
                    'amount': 27500,
                    'intended_recipient': None,
                    'prisoner_number': 'A1413AE', 'prisoner_name': 'NORMAN STANLEY FLETCHER',
                    'prison': 'LEI', 'prison_name': 'HMP LEEDS',
                    'sender_name': 'HEIDENREICH X',
                    'sender_sort_code': '219657', 'sender_account_number': '88447894',
                    'sender_roll_number': '', 'sender_email': None,
                    'card_number_last_digits': None, 'card_expiry_date': None,
                    'billing_address': None, 'ip_address': '127.0.0.1',
                    'resolution': 'credited', 'nomis_transaction_id': '123456-7',
                    'owner': None, 'owner_name': None,
                    'received_at': '2016-05-22T23:00:00Z',
                    'credited_at': '2016-05-23T01:10:00Z', 'refunded_at': None,
                },
            ]
        }
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/credits/'),
            json=response_data
        )

        expected_values = [
            self.expected_headers,
            ['GEORGE MELLEY', 'A1411AE', 'HMP LEEDS', None, 'Debit card', None, None, None,
             None, None, '102PF, London', '£230.00', '2016-05-25 21:24:00',
             'Credited', '2016-05-25 21:27:00', None, '127.0.0.1', 'ian@mail.local'],
            ['NORMAN STANLEY FLETCHER', 'A1413AE', 'HMP LEEDS', 'HEIDENREICH X',
             'Bank transfer', '21-96-57', '88447894', None, None, None, None,
             '£275.00', '2016-05-23 00:00:00',
             'Credited', '2016-05-23 02:10:00', '123456-7', '127.0.0.1', None]
        ]

        self.login()
        response = self.client.get(reverse('security:credits_export'))
        self.assertEqual(200, response.status_code)
        self.assertEqual('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', response['Content-Type'])

        self.assertSpreadsheetEqual(response.content, expected_values)

        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/credits/'),
            json=response_data
        )
        response = self.client.get(reverse('security:credits_email_export'), follow=False)
        self.assertRedirects(response, reverse('security:credit_list') + '?ordering=-received_at')
        self.assertSpreadsheetEqual(
            mail.outbox[0].attachments[0][1],
            expected_values,
            msg='Emailed contents do not match expected'
        )

    @responses.activate
    def test_no_data(self):
        sample_prison_list()
        response_data = {
            'count': 0,
            'previous': None,
            'next': None,
            'results': []
        }
        responses.add(
            responses.GET,
            api_url('/credits/'),
            json=response_data
        )

        expected_values = [self.expected_headers]

        self.login()
        response = self.client.get(reverse('security:credits_export'))
        self.assertEqual(200, response.status_code)
        self.assertEqual('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', response['Content-Type'])

        self.assertSpreadsheetEqual(response.content, expected_values)

        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/credits/'),
            json=response_data
        )
        response = self.client.get(reverse('security:credits_email_export'), follow=False)
        self.assertRedirects(response, reverse('security:credit_list') + '?ordering=-received_at')
        self.assertSpreadsheetEqual(
            mail.outbox[0].attachments[0][1],
            expected_values,
            msg='Emailed contents do not match expected'
        )

    @responses.activate
    def test_invalid_params_redirects_to_form(self):
        sample_prison_list()
        self.login()
        response = self.client.get(
            reverse('security:credits_export') + '?received_at__gte=LL'
        )
        self.assertRedirects(response, reverse('security:credit_list') + '?ordering=-received_at')

    def assertSpreadsheetEqual(self, spreadsheet_data, expected_values, msg=None):  # noqa: N802
        with temp_spreadsheet(spreadsheet_data) as ws:
            for i, row in enumerate(expected_values, start=1):
                for j, cell in enumerate(row, start=1):
                    self.assertEqual(cell, ws.cell(column=j, row=i).value, msg=msg)


class PinnedProfileTestCase(SecurityViewTestCase):

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
        response = self.login_test_searches()

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
        response = self.login_test_searches()

        self.assertContains(response, 'Saved search 1')
        self.assertNotContains(response, 'Saved search 2')
        self.assertContains(response, '3 new credits')


class PrisonerDetailViewTestCase(SecurityViewTestCase):
    def _add_prisoner_data_responses(self):
        responses.add(
            responses.GET,
            api_url('/prisoners/1/'),
            json=self.prisoner_profile,
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/1/credits/'),
            json={
                'count': 4,
                'results': [
                    self.credit_object, self.credit_object,
                    self.credit_object, self.credit_object
                ],
            },
        )

    @responses.activate
    @override_nomis_settings
    def test_display_nomis_photo(self):
        responses.add(
            responses.GET,
            nomis_url('/offenders/{prisoner_number}/image'.format(
                prisoner_number=self.prisoner_profile['prisoner_number'])),
            json={
                'image': TEST_IMAGE_DATA
            },
        )
        self.login(follow=False)
        response = self.client.get(
            reverse(
                'security:prisoner_image',
                kwargs={'prisoner_number': self.prisoner_profile['prisoner_number']}
            )
        )
        self.assertContains(response, base64.b64decode(TEST_IMAGE_DATA))

    @responses.activate
    @override_nomis_settings
    def test_missing_nomis_photo(self):
        responses.add(
            responses.GET,
            nomis_url('/offenders/{prisoner_number}/image'.format(
                prisoner_number=self.prisoner_profile['prisoner_number'])),
            json={
                'image': None
            },
        )
        self.login(follow=False)
        response = self.client.get(
            reverse(
                'security:prisoner_image',
                kwargs={'prisoner_number': self.prisoner_profile['prisoner_number']}
            ),
            follow=False
        )
        self.assertRedirects(response, '/static/images/placeholder-image.png', fetch_redirect_response=False)

    @responses.activate
    @override_nomis_settings
    def test_display_pinned_profile(self):
        self._add_prisoner_data_responses()
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 1,
                'results': [
                    {
                        'id': 1,
                        'description': 'Saved search 1',
                        'endpoint': '/prisoners/1/credits/',
                        'last_result_count': 2,
                        'site_url': '/en-gb/security/prisoners/1/?ordering=-received_at',
                        'filters': []
                    },
                ]
            },
        )
        responses.add(
            responses.PATCH,
            api_url('/searches/1/'),
            status=204,
        )
        self.login(follow=False)
        response = self.client.get(
            reverse('security:prisoner_detail', kwargs={'prisoner_id': 1})
        )
        self.assertContains(response, 'Stop monitoring this prisoner')
        self.assertEqual(responses.calls[-1].request.body, b'{"last_result_count": 4}')

    @responses.activate
    @override_nomis_settings
    def test_pin_profile(self):
        self._add_prisoner_data_responses()
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 0,
                'results': []
            },
        )
        responses.add(
            responses.POST,
            api_url('/searches/'),
            status=201,
        )

        self.login(follow=False)
        self.client.get(
            reverse('security:prisoner_detail', kwargs={'prisoner_id': 1}) +
            '?pin=1'
        )
        self.assertEqual(
            json.loads(responses.calls[-1].request.body.decode()),
            {
                'description': 'A1409AE JAMES HALLS',
                'endpoint': '/prisoners/1/credits/',
                'last_result_count': 4,
                'site_url': '/en-gb/security/prisoners/1/?ordering=-received_at',
                'filters': [{'field': 'ordering', 'value': '-received_at'}],
            },
        )
