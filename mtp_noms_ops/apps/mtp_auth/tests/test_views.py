import json

from django.conf import settings
from django.test import override_settings, SimpleTestCase
from django.urls import reverse
from mtp_common.test_utils import silence_logger
import responses


ZENDESK_BASE_URL = 'https://zendesk.mtp.local'


@override_settings(
    ZENDESK_BASE_URL=ZENDESK_BASE_URL,
)
class RequestAccessTestCase(SimpleTestCase):

    def setUp(self):
        self.account_request_valid_payload = {
            'first_name': 'My First Name',
            'last_name': 'My Last Name',
            'email': 'my-username@mtp.local',
            'username': 'my-username',
            'role': 'security',
            'manager_email': 'my-manager@mtp.local',
            'reason': 'because I need an account',
        }

    def test_request_account_first_request(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                f'{settings.API_URL}/requests/?username=my-username&role__name=security',
                json={'count': 0},
                status=200,
            )
            rsps.add(
                rsps.POST,
                f'{settings.API_URL}/requests/',
                json={},
                status=201,
            )

            response = self.client.post(
                reverse('sign-up'),
                data=self.account_request_valid_payload,
            )

            self.assertEqual(len(rsps.calls), 2)
            self.assertIn('role=security', rsps.calls[1].request.body)

        self.assertContains(response, 'Your request for access has been sent')

    def test_request_account_already_requested(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                f'{settings.API_URL}/requests/?username=my-username&role__name=security',
                json={'count': 1},
                status=200,
            )
            rsps.add(
                rsps.POST,
                f'{ZENDESK_BASE_URL}/api/v2/tickets.json',
            )

            response = self.client.post(
                reverse('sign-up'),
                data=self.account_request_valid_payload,
            )

            zendesk_request = rsps.calls[1].request
            zendesk_request_payload = json.loads(zendesk_request.body)

            self.maxDiff = None
            self.assertDictEqual(
                zendesk_request_payload,
                {
                    'ticket': {
                        'comment': {
                            'body': (
                                'Requesting a new staff account - Prisoner money intelligence\n'
                                '============================================================\n'
                                '\n'
                                'Reason for requesting account: because I need an account'
                                '\n'
                                '\n'
                                '---\n'
                                '\n'
                                'Forename: My First Name\n'
                                'Surname: My Last Name\n'
                                'Username (Quantum ID): my-username\n'
                                'Staff email: my-username@mtp.local\n'
                                'Account Type: security\n'
                                'Manager email: my-manager@mtp.local'
                            )
                        },
                        'custom_fields': [
                            {'id': 26047167, 'value': ''},
                            {'id': 29241738, 'value': 'my-username'},
                        ],
                        'group_id': 26417927,
                        'requester': {
                            'email': 'my-username@mtp.local',
                            'name': 'Sender: my-username',
                        },
                        'subject': 'MTP for digital team - Prisoner money intelligence - Request for new staff account',
                        'tags': ['feedback', 'mtp', 'noms-ops', 'account_request', settings.ENVIRONMENT],
                    },
                },
            )

        self.assertContains(response, 'Your request for access has been sent')

    def test_api_response_error(self):
        with responses.RequestsMock() as rsps, silence_logger():
            rsps.add(
                rsps.GET,
                f'{settings.API_URL}/requests/?username=my-username&role__name=security',
                status=500,
            )
            response = self.client.post(
                reverse('sign-up'),
                data=self.account_request_valid_payload,
            )

        self.assertContains(response, 'This service is currently unavailable')
