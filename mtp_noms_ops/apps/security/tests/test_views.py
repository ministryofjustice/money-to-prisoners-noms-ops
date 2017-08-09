import base64
from functools import wraps
import io
import json
import logging
from unittest import mock
import zipfile

from django.core import mail
from django.core.urlresolvers import reverse
from django.test import SimpleTestCase, override_settings
from mtp_common.auth.test_utils import generate_tokens
from mtp_common.test_utils import silence_logger
from slumber.exceptions import HttpNotFoundError, HttpServerError
import responses

from security import required_permissions
from security.tests import api_url, nomis_url, TEST_IMAGE_DATA
from security.tests.test_forms import mocked_prisons


def sample_prison_list(mocked_api_client):
    mocked_api_client().prisons.get.return_value = {
        'count': 2,
        'results': [
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
        ],
    }


def no_saved_searches(mocked_api_client):
    mocked_api_client.searches.get.return_value = {
        'count': 0,
        'results': []
    }


def mock_form_connection(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with mock.patch('security.forms.get_connection') as c:
            no_saved_searches(c())
            args += (c,)
            return f(*args, **kwargs)
    return wrapper


class SecurityBaseTestCase(SimpleTestCase):
    @mock.patch('mtp_noms_ops.urls.get_connection')
    @mock.patch('mtp_common.auth.backends.api_client')
    def login(self, mock_api_client, mocked_search_connection, follow=True):
        no_saved_searches(mocked_search_connection())
        return self._login(mock_api_client, follow=follow)

    @mock.patch('mtp_common.auth.backends.api_client')
    def login_test_searches(self, mock_api_client, follow=True):
        return self._login(mock_api_client, follow=follow)

    def _login(self, mock_api_client, follow=True):
        mock_api_client.authenticate.return_value = {
            'pk': 5,
            'token': generate_tokens(),
            'user_data': {
                'first_name': 'Sam',
                'last_name': 'Hall',
                'username': 'shall',
                'permissions': required_permissions,
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
    def test_can_access_security_dashboard(self):
        response = self.login()
        self.assertContains(response, '<!-- dashboard -->')

    @mock.patch('mtp_noms_ops.urls.get_connection')
    def test_cannot_access_prisoner_location_admin(self, mocked_search_connection):
        self.login()
        no_saved_searches(mocked_search_connection())
        response = self.client.get(reverse('location_file_upload'), follow=True)
        self.assertNotContains(response, '<!-- location_file_upload -->')
        self.assertContains(response, '<!-- dashboard -->')


class SecurityViewTestCase(SecurityBaseTestCase):
    view_name = None
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
        'recipient_names': ['Jim Halls', 'JAMES HALLS', 'James Halls '],
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

    def setUp(self):
        self.mocked_prison_data = mock.patch('security.models.retrieve_all_pages', return_value=mocked_prisons)
        self.mocked_prison_data.start()

    def tearDown(self):
        self.mocked_prison_data.stop()

    @mock_form_connection
    @mock.patch('security.forms.SecurityForm.get_object_list')
    def test_can_access_security_view(self, _, mocked_form_method):
        mocked_form_method.return_value = []
        if not self.view_name:
            return
        self.login()
        response = self.client.get(reverse(self.view_name), follow=True)
        self.assertContains(response, '<!-- %s -->' % self.view_name)


class SenderListTestCase(SecurityViewTestCase):
    view_name = 'security:sender_list'
    detail_view_name = 'security:sender_detail'

    def setUp(self):
        super().setUp()
        self.login()

    @mock_form_connection
    def test_displays_results(self, mocked_connection):
        mocked_connection().senders.get.return_value = {
            'count': 2,
            'results': [self.bank_transfer_sender, self.debit_card_sender],
        }

        response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'MAISIE NOLAN')
        response_content = response.content.decode(response.charset)
        self.assertIn('£410.00', response_content)
        self.assertIn('£420.00', response_content)

    @mock_form_connection
    def test_displays_bank_transfer_detail(self, mocked_connection):
        mocked_connection().senders().get.return_value = self.bank_transfer_sender
        mocked_connection().senders().credits.get.return_value = {
            'count': 4,
            'results': [self.credit_object, self.credit_object, self.credit_object, self.credit_object],
        }

        response = self.client.get(reverse(self.detail_view_name, kwargs={'sender_id': 9}))
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('MAISIE', response_content)
        self.assertIn('12312345', response_content)
        self.assertIn('James Halls', response_content)
        self.assertIn('£102.50', response_content)

    @mock_form_connection
    def test_displays_debit_card_detail(self, mocked_connection):
        mocked_connection().senders().get.return_value = self.debit_card_sender
        mocked_connection().senders().credits.get.return_value = {
            'count': 4,
            'results': [self.credit_object, self.credit_object, self.credit_object, self.credit_object],
        }

        response = self.client.get(reverse(self.detail_view_name, kwargs={'sender_id': 9}))
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('**** **** **** 1234', response_content)
        self.assertIn('10/20', response_content)
        self.assertIn('SW137NJ', response_content)
        self.assertIn('James Halls', response_content)
        self.assertIn('£102.50', response_content)

    @mock.patch('security.forms.get_connection')
    def test_detail_not_found(self, mocked_connection):
        mocked_connection().senders().get.side_effect = HttpNotFoundError
        mocked_connection().senders().credits.get.side_effect = HttpNotFoundError
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'sender_id': 9}))
        self.assertEqual(response.status_code, 404)

    @mock.patch('security.forms.get_connection')
    def test_connection_errors(self, mocked_connection):
        mocked_connection().senders.get.side_effect = HttpServerError
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'non-field-error')

        mocked_connection().senders().get.side_effect = HttpServerError
        mocked_connection().senders().credits.get.side_effect = HttpServerError
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'sender_id': 9}))
        self.assertContains(response, 'non-field-error')


class PrisonerListTestCase(SecurityViewTestCase):
    view_name = 'security:prisoner_list'
    detail_view_name = 'security:prisoner_detail'

    def setUp(self):
        super().setUp()
        self.login()

    @mock_form_connection
    def test_displays_results(self, mocked_connection):
        response_data = {
            'count': 1,
            'results': [self.prisoner_profile]
        }
        mocked_connection().prisoners.get.return_value = response_data

        response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'James Halls')
        response_content = response.content.decode(response.charset)
        self.assertIn('A1409AE', response_content)
        self.assertIn('310.00', response_content)

    @mock_form_connection
    def test_displays_detail(self, mocked_connection):
        mocked_connection().prisoners().get.return_value = self.prisoner_profile
        mocked_connection().prisoners().credits.get.return_value = {
            'count': 4,
            'results': [self.credit_object, self.credit_object, self.credit_object, self.credit_object],
        }

        response = self.client.get(reverse(self.detail_view_name, kwargs={'prisoner_id': 9}))
        self.assertContains(response, 'JAMES HALLS')
        response_content = response.content.decode(response.charset)
        self.assertIn('Jim Halls', response_content)
        self.assertNotIn('James Halls', response_content)
        self.assertIn('MAISIE', response_content)
        self.assertIn('£102.50', response_content)

    @mock.patch('security.forms.get_connection')
    def test_detail_not_found(self, mocked_connection):
        mocked_connection().prisoners().get.side_effect = HttpNotFoundError
        mocked_connection().prisoners().credits.get.side_effect = HttpNotFoundError
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'prisoner_id': 9}))
        self.assertEqual(response.status_code, 404)

    @mock.patch('security.forms.get_connection')
    def test_connection_errors(self, mocked_connection):
        mocked_connection().prisoners.get.side_effect = HttpServerError
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'non-field-error')

        mocked_connection().prisoners().get.side_effect = HttpServerError
        mocked_connection().prisoners().credits.get.side_effect = HttpServerError
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'prisoner_id': 9}))
        self.assertContains(response, 'non-field-error')


class CreditsListTestCase(SecurityViewTestCase):
    view_name = 'security:credit_list'

    @mock_form_connection
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
        response = self.client.get(reverse(self.view_name), {'ordering': '-amount'})
        self.assertContains(response, 'George Melley')
        response_content = response.content.decode(response.charset)
        self.assertIn('A1413AE', response_content)
        self.assertIn('275.00', response_content)
        self.assertIn('Bank transfer', response_content)
        self.assertIn('Debit card', response_content)


class CreditsExportTestCase(SecurityBaseTestCase):

    @mock.patch('security.tasks.get_connection_with_session')
    @mock.patch('security.forms.get_connection')
    def test_creates_csv(self, mocked_connection, mocked_connection_async):
        sample_prison_list(mocked_connection)
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
                    'billing_address': {'line1': '102PF', 'city': 'London'}, 'ip_address': '127.0.0.1',
                    'resolution': 'credited', 'nomis_transaction_id': None,
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
                    'card_number_last_digits': None, 'card_expiry_date': None,
                    'billing_address': None, 'ip_address': '127.0.0.1',
                    'resolution': 'credited', 'nomis_transaction_id': '123456-7',
                    'owner': None, 'owner_name': None,
                    'received_at': '2016-05-22T23:00:00Z', 'credited_at': '2016-05-23T01:10:00Z', 'refunded_at': None,
                },
            ]
        }
        mocked_connection().credits.get.return_value = response_data

        expected_result = (
            'Prisoner name,Prisoner number,Prison,Sender name,Payment method,'
            'Bank transfer sort code,Bank transfer account,Bank transfer roll number,'
            'Debit card number,Debit card expiry,Address,Amount,Date received,'
            'Credited status,Date credited,NOMIS ID,IP\r\n'
            'GEORGE MELLEY,A1411AE,HMP LEEDS,,Debit card,,,,,,'
            '"102PF, London",£230.00,2016-05-25 21:24:00,'
            'Credited,2016-05-25 21:27:00,,127.0.0.1\r\n'
            'NORMAN STANLEY FLETCHER,A1413AE,HMP LEEDS,HEIDENREICH X,Bank transfer,21-96-57,88447894,,,,'
            ',£275.00,2016-05-23 00:00:00,'
            'Credited,2016-05-23 02:10:00,123456-7,127.0.0.1\r\n'
        )

        self.login()
        response = self.client.get(reverse('security:credits_export'))
        self.assertEqual(200, response.status_code)
        self.assertEqual('text/csv', response['Content-Type'])
        self.assertEqual(expected_result, response.content.decode(response.charset))

        no_saved_searches(mocked_connection())
        mocked_connection_async().credits.get.return_value = response_data
        response = self.client.get(reverse('security:credits_email_export'), follow=False)
        self.assertRedirects(response, reverse('security:credit_list') + '?ordering=-received_at')
        self.assertZipDataEqual(mail.outbox[0].attachments[0][1], expected_result)

    @mock.patch('security.tasks.get_connection_with_session')
    @mock.patch('security.forms.get_connection')
    def test_no_data(self, mocked_connection, mocked_connection_async):
        sample_prison_list(mocked_connection)
        response_data = {
            'count': 0,
            'previous': None,
            'next': None,
            'results': []
        }
        mocked_connection().credits.get.return_value = response_data

        expected_result = (
            'Prisoner name,Prisoner number,Prison,Sender name,Payment method,'
            'Bank transfer sort code,Bank transfer account,Bank transfer roll number,'
            'Debit card number,Debit card expiry,Address,Amount,Date received,'
            'Credited status,Date credited,NOMIS ID,IP\r\n'
        )

        self.login()
        response = self.client.get(reverse('security:credits_export'))
        self.assertEqual(200, response.status_code)
        self.assertEqual('text/csv', response['Content-Type'])
        self.assertEqual(expected_result, response.content.decode(response.charset))

        no_saved_searches(mocked_connection())
        mocked_connection_async().credits.get.return_value = response_data
        response = self.client.get(reverse('security:credits_email_export'), follow=False)
        self.assertRedirects(response, reverse('security:credit_list') + '?ordering=-received_at')
        self.assertZipDataEqual(mail.outbox[0].attachments[0][1], expected_result)

    @mock_form_connection
    def test_invalid_params_redirects_to_form(self, mocked_connection):
        sample_prison_list(mocked_connection)
        self.login()
        response = self.client.get(
            reverse('security:credits_export') + '?received_at__gte=LL'
        )
        self.assertRedirects(response, reverse('security:credit_list') + '?ordering=-received_at')

    def assertZipDataEqual(self, zip_data, expected_csv):  # noqa
        zip_data = io.BytesIO(zip_data)
        with zipfile.ZipFile(zip_data, 'r') as zip_file:
            contents = zip_file.namelist()
            self.assertEqual(len(contents), 1, msg='Zip should contain exactly 1 file')
            with zip_file.open(contents[0]) as contents:
                contents = contents.read().decode()
        self.assertEqual(contents, expected_csv, msg='Zipped contents do not match expected')


class PinnedProfileTestCase(SecurityViewTestCase):

    def test_pinned_profiles_on_dashboard(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
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
            rsps.add(
                rsps.GET,
                api_url('/prisoners/1/credits/'),
                json={
                    'count': 5,
                    'results': []
                },
            )
            rsps.add(
                rsps.GET,
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

    def test_removes_invalid_saved_searches(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
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
            rsps.add(
                rsps.GET,
                api_url('/prisoners/1/credits/'),
                json={
                    'count': 5,
                    'results': []
                },
            )
            rsps.add(
                rsps.GET,
                api_url('/senders/1/credits/'),
                status=404,
            )
            rsps.add(
                rsps.DELETE,
                api_url('/searches/2/'),
                status=201,
            )
            response = self.login_test_searches()

        self.assertContains(response, 'Saved search 1')
        self.assertNotContains(response, 'Saved search 2')
        self.assertContains(response, '3 new credits')


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


class PrisonerDetailViewTestCase(SecurityViewTestCase):
    def _add_prisoner_data_responses(self, rsps):
        rsps.add(
            rsps.GET,
            api_url('/prisoners/1/'),
            json=self.prisoner_profile,
        )
        rsps.add(
            rsps.GET,
            api_url('/prisoners/1/credits/'),
            json={
                'count': 4,
                'results': [
                    self.credit_object, self.credit_object,
                    self.credit_object, self.credit_object
                ],
            },
        )

    @override_nomis_settings
    def test_display_nomis_photo(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
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

    @override_nomis_settings
    def test_missing_nomis_photo(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
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

    def test_display_pinned_profile(self):
        with responses.RequestsMock() as rsps:
            self._add_prisoner_data_responses(rsps)
            rsps.add(
                rsps.GET,
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
            rsps.add(
                rsps.PATCH,
                api_url('/searches/1/'),
                status=204,
            )
            self.login(follow=False)
            response = self.client.get(
                reverse('security:prisoner_detail', kwargs={'prisoner_id': 1})
            )
            self.assertContains(response, 'Stop monitoring this prisoner')
            self.assertEqual(rsps.calls[-1].request.body, '{"last_result_count": 4}')

    def test_pin_profile(self):
        with responses.RequestsMock() as rsps:
            self._add_prisoner_data_responses(rsps)
            rsps.add(
                rsps.GET,
                api_url('/searches/'),
                json={
                    'count': 0,
                    'results': []
                },
            )
            rsps.add(
                rsps.POST,
                api_url('/searches/'),
                status=201,
            )

            self.login(follow=False)
            self.client.get(
                reverse('security:prisoner_detail', kwargs={'prisoner_id': 1}) +
                '?pin=1'
            )
            self.assertEqual(
                json.loads(rsps.calls[-1].request.body),
                {
                    'description': 'A1409AE JAMES HALLS',
                    'endpoint': '/prisoners/1/credits/',
                    'last_result_count': 4,
                    'site_url': '/en-gb/security/prisoners/1/?ordering=-received_at',
                    'filters': [{'field': 'ordering', 'value': '-received_at'}],
                },
            )
