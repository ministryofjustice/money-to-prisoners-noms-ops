from django.core.urlresolvers import reverse
import responses

from security.tests.utils import api_url
from security.tests.views.test_base import (
    ExportSecurityViewTestCaseMixin,
    sample_prison_list,
    SecurityViewTestCase,
    SimpleSearchV2SecurityTestCaseMixin,
)


class DisbursementViewsTestCase(SecurityViewTestCase):
    """
    TODO: delete after search V2 goes live.
    """
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


class DisbursementViewsV2TestCase(
    SimpleSearchV2SecurityTestCaseMixin,
    ExportSecurityViewTestCaseMixin,
    SecurityViewTestCase,
):
    """
    Test case related to disbursement search V2 and detail views.
    """
    view_name = 'security:disbursement_list'
    search_results_view_name = 'security:disbursement_search_results'
    detail_view_name = 'security:disbursement_detail'
    search_ordering = '-created'
    api_list_path = '/disbursements/'

    bank_transfer_disbursement = {
        'id': 99,
        'created': '2018-02-12T12:00:00Z',
        'modified': '2018-02-12T12:00:00Z',
        'method': 'bank_transfer',
        'amount': 2000,
        'resolution': 'sent',
        'nomis_transaction_id': '1234567-1',
        'invoice_number': '1000099',
        'prisoner_number': 'A1409AE',
        'prisoner_name': 'JAMES HALLS',
        'prison': 'ABC',
        'prison_name': 'HMP Test1',
        'recipient_first_name': 'Jack',
        'recipient_last_name': 'Halls',
        'recipient_email': '',
        'remittance_description': '',
        'address_line1': '102 Petty France',
        'address_line2': '',
        'city': 'London',
        'postcode': 'SW1H 9AJ',
        'country': None,
        'account_number': '1234567',
        'sort_code': '112233',
        'roll_number': None,
        'comments': [],
        'log_set': [
            {
                'action': 'created',
                'created': '2018-02-12T10:00:00Z',
                'user': {'first_name': 'Mary', 'last_name': 'Smith', 'username': 'msmith'}
            },
            {
                'action': 'confirmed',
                'created': '2018-02-12T11:00:00Z',
                'user': {'first_name': 'John', 'last_name': 'Smith', 'username': 'jsmith'}
            },
            {
                'action': 'sent',
                'created': '2018-02-12T12:00:00Z',
                'user': {'first_name': 'SSCL', 'last_name': '', 'username': 'sscl'}
            }
        ],
    }

    cheque_disbursement = {
        'id': 100,
        'created': '2018-02-10T10:00:00Z',
        'modified': '2018-02-10T12:00:00Z',
        'method': 'cheque',
        'amount': 1000,
        'resolution': 'confirmed',
        'nomis_transaction_id': '1234568-1',
        'prisoner_number': 'A1401AE',
        'prisoner_name': 'JILLY HALL',
        'prison': 'DEF',
        'prison_name': 'HMP Test2',
        'recipient_first_name': 'Jilly',
        'recipient_last_name': 'Halls',
        'recipient_email': 'jilly@mtp.local',
        'remittance_description': 'PRESENT',
        'address_line1': '102 Petty France',
        'address_line2': '',
        'city': 'London',
        'postcode': 'SW1H 9AJ',
        'country': None,
        'account_number': '',
        'sort_code': '',
        'roll_number': None,
        'comments': [],
        'log_set': [
            {
                'action': 'created',
                'created': '2018-02-10T01:00:00Z',
                'user': {'first_name': 'Mary', 'last_name': 'Smith', 'username': 'msmith'}
            },
            {
                'action': 'confirmed',
                'created': '2018-02-10T02:00:00Z',
                'user': {'first_name': 'John', 'last_name': 'Smith', 'username': 'jsmith'}
            }
        ],
    }

    export_view_name = 'security:disbursements_export'
    export_email_view_name = 'security:disbursements_email_export'
    export_expected_xls_headers = [
        'Prisoner name',
        'Prisoner number',
        'Prison',
        'Recipient first name',
        'Recipient last name',
        'Payment method',
        'Address',
        'Recipient email',
        'Bank transfer sort code',
        'Bank transfer account',
        'Bank transfer roll number',
        'Amount',
        'Status',
        'Date entered',
        'Date confirmed',
        'Date sent',
        'NOMIS ID',
    ]
    export_expected_xls_rows = [
        [
            'JAMES HALLS',
            'A1409AE',
            'HMP Test1',
            'Jack',
            'Halls',
            'Bank transfer',
            '102 Petty France, London, SW1H 9AJ',
            None,
            '11-22-33',
            '1234567',
            None,
            '£20.00',
            'Sent',
            '2018-02-12 12:00:00',
            '2018-02-12 11:00:00',
            '2018-02-12 12:00:00',
            '1234567-1',
        ],
        [
            'JILLY HALL',
            'A1401AE',
            'HMP Test2',
            'Jilly',
            'Halls',
            'Cheque',
            '102 Petty France, London, SW1H 9AJ',
            'jilly@mtp.local',
            None,
            None,
            None,
            '£10.00',
            'Confirmed',
            '2018-02-10 10:00:00',
            '2018-02-10 02:00:00',
            None,
            '1234568-1',
        ],
    ]

    def _test_simple_search_search_results_content(self, response):
        self.assertContains(response, '2 disbursements')

        self.assertContains(response, 'Jack Halls')
        self.assertContains(response, '20.00')
        self.assertContains(response, 'A1409AE')

        self.assertContains(response, 'Jilly Halls')
        self.assertContains(response, '10.00')
        self.assertContains(response, 'A1401AE')

    def test_detail_view_displays_bank_transfer_detail(self):
        disbursement_id = 99
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/disbursements/{disbursement_id}/'),
                json=self.bank_transfer_disbursement,
            )

            self.login(rsps=rsps)
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'disbursement_id': disbursement_id},
                ),
            )
        self.assertContains(response, 'Bank transfer')
        self.assertContains(response, '20.00')
        self.assertContains(response, 'JAMES HALLS')
        self.assertContains(response, 'Jack Halls')
        self.assertContains(response, '1234567-1')
        self.assertContains(response, '1000099')
        self.assertContains(response, 'Confirmed by John Smith')
        self.assertContains(response, 'None given')

    def test_detail_view_displays_cheque_detail(self):
        disbursement_id = 100
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/disbursements/{disbursement_id}/'),
                json=self.cheque_disbursement,
            )

            self.login(rsps=rsps)
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'disbursement_id': disbursement_id},
                ),
            )
        self.assertContains(response, 'Cheque')
        self.assertContains(response, '10.00')
        self.assertContains(response, 'JILLY HALL')
        self.assertContains(response, 'Jilly Halls')
        self.assertContains(response, '1234568-1')
        self.assertContains(response, 'Confirmed by John Smith')
        self.assertContains(response, 'jilly@mtp.local')
        self.assertContains(response, 'PRESENT')

    def get_api_object_list_response_data(self):
        return [
            self.bank_transfer_disbursement,
            self.cheque_disbursement,
        ]
