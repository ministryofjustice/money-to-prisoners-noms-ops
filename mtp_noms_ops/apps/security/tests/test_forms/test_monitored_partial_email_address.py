from unittest import mock
from urllib.parse import parse_qs

from django.test import SimpleTestCase
from mtp_common.auth.test_utils import generate_tokens
from mtp_common.test_utils import silence_logger
import responses
from responses.matchers import json_params_matcher

from security.forms.monitored_partial_email_address import (
    MonitoredPartialEmailAddressListForm,
    MonitoredPartialEmailAddressAddForm,
    MonitoredPartialEmailAddressDeleteForm,
)
from security.tests import api_url, mock_empty_response


class MonitoredPartialEmailAddressBaseTestCase(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens(),
            ),
        )


class MonitoredPartialEmailAddressListFormTestCase(MonitoredPartialEmailAddressBaseTestCase):
    def test_get_object_list(self):
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


class MonitoredPartialEmailAddressAddFormTestCase(MonitoredPartialEmailAddressBaseTestCase):
    def test_add_keyword(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.POST,
                api_url('/security/monitored-email-addresses/'),
                match=[json_params_matcher(params='Mouse')],
                status=201,
                body=b'mouse',
            )

            form = MonitoredPartialEmailAddressAddForm(self.request, data={'keyword': 'Mouse '})
            self.assertTrue(form.is_valid())
            self.assertTrue(form.add_keyword())

    def test_invalid_form(self):
        with responses.RequestsMock():
            form = MonitoredPartialEmailAddressAddForm(self.request, data={'keyword': 'M'})
            self.assertFalse(form.is_valid())

    def test_error_response(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.POST,
                api_url('/security/monitored-email-addresses/'),
                status=400,
                json={'keyword': ['Keyword already exists.']},
            )

            form = MonitoredPartialEmailAddressAddForm(self.request, data={'keyword': 'mouse'})
            self.assertTrue(form.is_valid())
            with silence_logger():
                self.assertFalse(form.add_keyword())


class MonitoredPartialEmailAddressDeleteFormTestCase(MonitoredPartialEmailAddressBaseTestCase):
    def test_delete_keyword(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.DELETE,
                api_url('/security/monitored-email-addresses/cat%20and%2For%20dog/'),
                status=204,
                body=b'',
            )

            form = MonitoredPartialEmailAddressDeleteForm(self.request, data={'keyword': 'cat and/or dog'})
            self.assertTrue(form.is_valid())
            self.assertTrue(form.delete_keyword())

    def test_error_response(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.DELETE,
                api_url('/security/monitored-email-addresses/cat%20and%2For%20dog/'),
                status=404,
                body=b'',
            )

            form = MonitoredPartialEmailAddressDeleteForm(self.request, data={'keyword': 'cat and/or dog'})
            self.assertTrue(form.is_valid())
            with silence_logger():
                self.assertFalse(form.delete_keyword())
