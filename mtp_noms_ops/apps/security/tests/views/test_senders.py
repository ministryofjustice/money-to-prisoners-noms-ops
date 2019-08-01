from django.core.urlresolvers import reverse
from mtp_common.test_utils import silence_logger
import responses

from security.tests.utils import api_url
from security.tests.views.test_base import (
    ExportSecurityViewTestCaseMixin,
    no_saved_searches,
    sample_prison_list,
    SecurityViewTestCase,
    SimpleSearchV2SecurityTestCaseMixin,
)


class SenderViewsTestCase(SecurityViewTestCase):
    """
    TODO: delete after search V2 goes live.
    """
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


class SenderViewsV2TestCase(
    SimpleSearchV2SecurityTestCaseMixin,
    ExportSecurityViewTestCaseMixin,
    SecurityViewTestCase,
):
    """
    Test case related to sender search V2 and detail views.
    """
    view_name = 'security:sender_list'
    search_results_view_name = 'security:sender_search_results'
    detail_view_name = 'security:sender_detail'
    search_ordering = '-prisoner_count'
    api_list_path = '/senders/'

    export_view_name = 'security:senders_export'
    export_email_view_name = 'security:senders_email_export'
    export_expected_xls_headers = [
        'Sender name',
        'Payment source',
        'Credits sent',
        'Total amount sent',
        'Prisoners sent to',
        'Prisons sent to',
        'Bank transfer sort code',
        'Bank transfer account',
        'Bank transfer roll number',
        'Debit card number',
        'Debit card expiry',
        'Debit card postcode',
        'Other cardholder names',
        'Cardholder emails',
    ]
    export_expected_xls_rows = [
        [
            'MAISIE NOLAN',
            'Bank transfer',
            4,
            '£410.00',
            3,
            2,
            '10-10-10',
            '12312345',
            None,
            None,
            None,
            None,
            None,
            None,
        ],
        [
            'Maisie N',
            'Debit card',
            4,
            '£420.00',
            3,
            2,
            None,
            None,
            None,
            '**** **** **** 1234',
            '10/20',
            'SW137NJ',
            'Maisie Nolan',
            'm@outside.local, mn@outside.local',
        ]
    ]

    def get_api_object_list_response_data(self):
        return [
            self.bank_transfer_sender,
            self.debit_card_sender,
        ]

    def _test_simple_search_search_results_content(self, response):
        self.assertContains(response, '2 payment sources')
        self.assertContains(response, 'MAISIE NOLAN')
        response_content = response.content.decode(response.charset)
        self.assertIn('£410.00', response_content)
        self.assertIn('£420.00', response_content)

    def test_detail_view_displays_bank_transfer_detail(self):
        sender_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/'),
                json=self.bank_transfer_sender,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/credits/'),
                json={
                    'count': 4,
                    'results': [self.credit_object] * 4,
                },
            )

            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'sender_id': sender_id},
                ),
            )
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('MAISIE', response_content)
        self.assertIn('12312345', response_content)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('£102.50', response_content)

    def test_detail_view_displays_debit_card_detail(self):
        sender_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/'),
                json=self.debit_card_sender,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/credits/'),
                json={
                    'count': 4,
                    'results': [self.credit_object] * 4,
                }
            )
            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'sender_id': sender_id},
                ),
            )
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('**** **** **** 1234', response_content)
        self.assertIn('10/20', response_content)
        self.assertIn('SW137NJ', response_content)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('£102.50', response_content)

    def test_detail_not_found(self):
        sender_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/'),
                status=404,
            )
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'sender_id': sender_id},
                    ),
                )
        self.assertEqual(response.status_code, 404)

    def test_connection_errors(self):
        sender_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            sample_prison_list(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(self.api_list_path),
                status=500,
            )
            with silence_logger('django.request'):
                response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'non-field-error')

        with responses.RequestsMock() as rsps:
            no_saved_searches(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/'),
                status=500,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/senders/{sender_id}/credits/'),
                status=500,
            )
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'sender_id': sender_id},
                    ),
                )
        self.assertContains(response, 'non-field-error')
