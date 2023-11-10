import datetime
from unittest import mock
from urllib.parse import parse_qs

from django.test import SimpleTestCase
from django.utils.timezone import make_aware
from mtp_common.auth.test_utils import generate_tokens
import responses

from security.forms.monitored_partial_email_address import MonitoredPartialEmailAddressListForm
from security.tests import mock_empty_response


class MonitoredPartialEmailAddressListFormTestCase(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens(),
            ),
        )

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_get_object_list(self, mock_get_need_attention_date):
        mock_get_need_attention_date.return_value = make_aware(datetime.datetime(2019, 7, 9, 9))

        with responses.RequestsMock() as rsps:
            mock_empty_response(rsps, '/security/checks/')
            mock_empty_response(rsps, '/security/monitored-email-addresses/')

            form = MonitoredPartialEmailAddressListForm(
                self.request,
                data={
                    'page': 2,
                },
            )

            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])

            monitored_emails_request, my_list_request = rsps.calls

        self.assertDictEqual(
            parse_qs(monitored_emails_request.request.url.split('?', 1)[1]),
            {
                'offset': ['20'],
                'limit': ['20'],
            },
        )
        self.assertDictEqual(
            parse_qs(my_list_request.request.url.split('?', 1)[1]),
            {
                'offset': ['0'],
                'limit': ['1'],
                'status': ['pending'],
                'credit_resolution': ['initial'],
            },
        )
