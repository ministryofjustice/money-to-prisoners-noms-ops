from django.core.urlresolvers import reverse
from mtp_common.test_utils import silence_logger
import responses

from security.tests.utils import api_url
from security.tests.views.test_base import (
    ExportSecurityViewTestCaseMixin,
    sample_prison_list,
    SecurityViewTestCase,
    SimpleSearchV2SecurityTestCaseMixin,
)


class CreditViewsTestCase(SecurityViewTestCase):
    """
    TODO: delete after search V2 goes live.
    """
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


class CreditViewsV2TestCase(
    SimpleSearchV2SecurityTestCaseMixin,
    ExportSecurityViewTestCaseMixin,
    SecurityViewTestCase,
):
    """
    Test case related to credit search V2 and detail views.
    """
    view_name = 'security:credit_list'
    search_results_view_name = 'security:credit_search_results'
    detail_view_name = 'security:credit_detail'
    search_ordering = '-received_at'
    api_list_path = '/credits/'

    debit_card_credit = {
        'id': 1,
        'source': 'online',
        'amount': 23000,
        'intended_recipient': 'Mr G Melley',
        'prisoner_number': 'A1411AE',
        'prisoner_name': 'GEORGE MELLEY',
        'prison': 'LEI',
        'prison_name': 'HMP LEEDS',
        'sender_name': None,
        'sender_sort_code': None,
        'sender_account_number': None,
        'sender_email': 'ian@mail.local',
        'billing_address': {'line1': '102PF', 'city': 'London'},
        'sender_roll_number': None,
        'card_number_last_digits': '4444',
        'card_expiry_date': '07/18',
        'resolution': 'credited',
        'owner': None,
        'owner_name': 'Maria',
        'received_at': '2016-05-25T20:24:00Z',
        'credited_at': '2016-05-25T20:27:00Z',
        'refunded_at': None,
        'comments': [{'user_full_name': 'Eve', 'comment': 'OK'}],
        'nomis_transaction_id': None,
        'ip_address': '127.0.0.1',
    }
    bank_transfer_credit = {
        'id': 2,
        'source': 'bank_transfer',
        'amount': 27500,
        'intended_recipient': None,
        'prisoner_number': 'A1413AE',
        'prisoner_name': 'NORMAN STANLEY FLETCHER',
        'prison': 'LEI',
        'prison_name': 'HMP LEEDS',
        'sender_name': 'HEIDENREICH X',
        'sender_email': None,
        'billing_address': None,
        'sender_sort_code': '219657',
        'sender_account_number': '88447894',
        'card_number_last_digits': None,
        'card_expiry_date': None,
        'sender_roll_number': '',
        'resolution': 'credited',
        'owner': None,
        'owner_name': 'Maria',
        'received_at': '2016-05-22T23:00:00Z',
        'credited_at': '2016-05-23T01:10:00Z',
        'refunded_at': None,
        'comments': [],
        'nomis_transaction_id': '123456-7',
        'ip_address': '127.0.0.1',
    }

    export_view_name = 'security:credits_export'
    export_email_view_name = 'security:credits_email_export'
    export_expected_xls_headers = [
        'Prisoner name',
        'Prisoner number',
        'Prison',
        'Sender name',
        'Payment method',
        'Bank transfer sort code',
        'Bank transfer account',
        'Bank transfer roll number',
        'Debit card number',
        'Debit card expiry',
        'Address',
        'Amount',
        'Date received',
        'Credited status',
        'Date credited',
        'NOMIS ID',
        'IP',
    ]
    export_expected_xls_rows = [
        [
            'GEORGE MELLEY',
            'A1411AE',
            'HMP LEEDS',
            None,
            'Debit card',
            None,
            None,
            None,
            '**** **** **** 4444',
            '07/18',
            '102PF, London',
            '£230.00',
            '2016-05-25 21:24:00',
            'Credited',
            '2016-05-25 21:27:00',
            None,
            '127.0.0.1',
            'ian@mail.local'
        ],
        [
            'NORMAN STANLEY FLETCHER',
            'A1413AE',
            'HMP LEEDS',
            'HEIDENREICH X',
            'Bank transfer',
            '21-96-57',
            '88447894',
            None,
            None,
            None,
            None,
            '£275.00',
            '2016-05-23 00:00:00',
            'Credited',
            '2016-05-23 02:10:00',
            '123456-7',
            '127.0.0.1',
            None
        ],
    ]

    def _test_simple_search_search_results_content(self, response):
        self.assertContains(response, '2 credits')

        self.assertContains(response, 'GEORGE MELLEY')
        self.assertContains(response, 'A1411AE')
        self.assertContains(response, '230.00')

        self.assertContains(response, 'NORMAN STANLEY FLETCHER')
        self.assertContains(response, 'A1413AE')
        self.assertContains(response, '275.00')

    def test_detail_view_displays_debit_card_detail(self):
        credit_id = 2
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                f'{api_url(self.api_list_path)}?pk={credit_id}',
                json={
                    'count': 1,
                    'previous': None,
                    'next': None,
                    'results': [self.debit_card_credit],
                }
            )

            self.login(rsps=rsps)
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'credit_id': credit_id},
                ),
            )
        self.assertContains(response, 'Debit card')
        response_content = response.content.decode(response.charset)
        self.assertIn('£230.00', response_content)
        self.assertIn('GEORGE MELLEY', response_content)
        self.assertIn('Mr G Melley', response_content)
        self.assertIn('A1411AE', response_content)
        self.assertIn('Credited by Maria', response_content)
        self.assertIn('Eve', response_content)
        self.assertIn('OK', response_content)

    def test_detail_view_displays_bank_transfer_detail(self):
        credit_id = 2
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                f'{api_url(self.api_list_path)}?pk={credit_id}',
                json={
                    'count': 1,
                    'previous': None,
                    'next': None,
                    'results': [self.bank_transfer_credit],
                }
            )

            self.login(rsps=rsps)
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'credit_id': credit_id},
                ),
            )
        self.assertContains(response, 'Bank transfer')
        response_content = response.content.decode(response.charset)
        self.assertIn('£275.00', response_content)
        self.assertIn('NORMAN STANLEY FLETCHER', response_content)
        self.assertIn('21-96-57', response_content)
        self.assertIn('88447894', response_content)
        self.assertIn('Credited by Maria', response_content)

    def test_detail_not_found(self):
        credit_id = 999
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                f'{api_url(self.api_list_path)}?pk={credit_id}',
                json={
                    'count': 0,
                    'previous': None,
                    'next': None,
                    'results': [],
                }
            )

            self.login(rsps=rsps)
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'credit_id': credit_id},
                    ),
                )
        self.assertEqual(response.status_code, 404)

    def get_api_object_list_response_data(self):
        return [
            self.debit_card_credit,
            self.bank_transfer_credit,
        ]
