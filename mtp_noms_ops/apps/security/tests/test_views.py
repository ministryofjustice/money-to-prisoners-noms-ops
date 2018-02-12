import base64
from contextlib import contextmanager
import json
import logging
import tempfile
from unittest import mock

from django.core import mail
from django.core.urlresolvers import reverse
from django.test import SimpleTestCase, override_settings
from mtp_common.auth.test_utils import generate_tokens
from mtp_common.test_utils import silence_logger
from openpyxl import load_workbook
import responses

from security import required_permissions
from security.tests import api_url, nomis_url, TEST_IMAGE_DATA


def sample_prison_list():
    responses.add(
        responses.GET,
        api_url('/prisons/'),
        json={
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


class SecurityBaseTestCase(SimpleTestCase):

    @mock.patch('mtp_common.auth.backends.api_client')
    def login(self, mock_api_client, follow=True):
        no_saved_searches()
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
                'prisons': [{'nomis_id': 'BXI', 'name': 'HMP Brixton', 'pre_approval_required': False}],
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

    @responses.activate
    @mock.patch('security.forms.SecurityForm.get_object_list')
    def test_can_access_security_view(self, mocked_form_method):
        mocked_form_method.return_value = []
        if not self.view_name:
            return
        sample_prison_list()
        self.login()
        response = self.client.get(reverse(self.view_name), follow=True)
        self.assertContains(response, '<!-- %s -->' % self.view_name)


class SenderListTestCase(SecurityViewTestCase):
    view_name = 'security:sender_list'
    detail_view_name = 'security:sender_detail'

    @responses.activate
    def setUp(self):
        super().setUp()
        self.login()

    @responses.activate
    def test_displays_results(self):
        no_saved_searches()
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/senders/'),
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

    @responses.activate
    def setUp(self):
        super().setUp()
        self.login()

    @responses.activate
    def test_displays_results(self):
        no_saved_searches()
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/prisoners/'),
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
    def test_displays_detail(self):
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

    @responses.activate
    def test_displays_results(self):
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/credits/'),
            json={
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
                        'sender_sort_code': None, 'sender_account_number': None,
                        'sender_roll_number': None,
                        'card_number_last_digits': '4444', 'card_expiry_date': '07/18',
                        'resolution': 'credited',
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
                        'sender_roll_number': '', 'resolution': 'credited',
                        'owner': None, 'owner_name': None,
                        'received_at': '2016-05-22T23:00:00Z',
                        'credited_at': '2016-05-23T01:10:00Z', 'refunded_at': None,
                    },
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


@override_settings(DISBURSEMENT_PRISONS=['BXI'])
class DisbursementsListTestCase(SecurityViewTestCase):
    view_name = 'security:disbursement_list'

    @responses.activate
    def test_displays_results(self):
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/disbursements/'),
            json={
                'count': 2,
                'previous': None,
                'next': 'http://localhost:8000/disbursements/?limit=20&offset=20&ordering=-amount',
                'results': [
                    {
                        'id': 1,
                        'created': '2018-02-12T12:00:00Z', 'modified': '2018-02-12T12:00:00Z',
                        'method': 'bank_transfer',
                        'amount': 2000,
                        'resolution': 'sent',
                        'nomis_transaction_id': '1234567-1',
                        'prisoner_number': 'A1409AE', 'prisoner_name': 'JAMES HALLS',
                        'prison': 'ABC', 'prison_name': 'HMP Test1',
                        'recipient_first_name': 'Jack', 'recipient_last_name': 'Halls', 'recipient_email': '',
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
                    },
                    {
                        'id': 2,
                        'created': '2018-02-10T10:00:00Z', 'modified': '2018-02-10T12:00:00Z',
                        'method': 'cheque',
                        'amount': 1000,
                        'resolution': 'confirmed',
                        'nomis_transaction_id': '1234568-1',
                        'prisoner_number': 'A1401AE', 'prisoner_name': 'JILLY HALL',
                        'prison': 'DEF', 'prison_name': 'HMP Test2',
                        'recipient_first_name': 'Jilly', 'recipient_last_name': 'Halls', 'recipient_email': '',
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
                    },
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
                    'billing_address': {'line1': '102PF', 'city': 'London'}, 'ip_address': '127.0.0.1',
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
                    'sender_sort_code': '219657', 'sender_account_number': '88447894', 'sender_roll_number': '',
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
             'Credited', '2016-05-25 21:27:00', None, '127.0.0.1'],
            ['NORMAN STANLEY FLETCHER', 'A1413AE', 'HMP LEEDS', 'HEIDENREICH X',
             'Bank transfer', '21-96-57', '88447894', None, None, None, None,
             '£275.00', '2016-05-23 00:00:00',
             'Credited', '2016-05-23 02:10:00', '123456-7', '127.0.0.1']
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

    def assertSpreadsheetEqual(self, spreadsheet_data, expected_values, msg=None):  # noqa
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
            json.loads(responses.calls[-1].request.body.decode('utf-8')),
            {
                'description': 'A1409AE JAMES HALLS',
                'endpoint': '/prisoners/1/credits/',
                'last_result_count': 4,
                'site_url': '/en-gb/security/prisoners/1/?ordering=-received_at',
                'filters': [{'field': 'ordering', 'value': '-received_at'}],
            },
        )
