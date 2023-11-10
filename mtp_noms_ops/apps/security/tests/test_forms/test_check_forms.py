import datetime
import json
from unittest import mock
from urllib.parse import parse_qs

from django.test import SimpleTestCase
from django.utils.timezone import make_aware
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _
from mtp_common.auth.test_utils import generate_tokens
from mtp_common.test_utils import silence_logger
import responses

from security.forms.check import AcceptOrRejectCheckForm, CheckListForm, AssignCheckToUserForm
from security.tests import api_url, mock_empty_response


class CheckListFormTestCase(SimpleTestCase):
    """
    Tests related to the CheckListForm.
    """

    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens(),
            ),
        )

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_get_object_list(self, mock_get_need_attention_date):
        """
        Test that the form makes the right API call to get the list of checks.
        """
        mock_get_need_attention_date.return_value = make_aware(datetime.datetime(2019, 7, 9, 9))

        with responses.RequestsMock() as rsps:
            mock_empty_response(rsps, '/security/checks/')

            form = CheckListForm(
                self.request,
                data={
                    'page': 2,
                },
            )

            self.assertTrue(form.is_valid())
            self.assertListEqual(form.get_object_list(), [])

            checks_request, needs_attention_request, my_list_request = rsps.calls

            self.assertDictEqual(
                parse_qs(checks_request.request.url.split('?', 1)[1]),
                {
                    'offset': ['20'],
                    'limit': ['20'],
                    'status': ['pending'],
                    'credit_resolution': ['initial'],
                },
            )
            self.assertDictEqual(
                parse_qs(needs_attention_request.request.url.split('?', 1)[1]),
                {
                    'offset': ['0'],
                    'limit': ['1'],
                    'status': ['pending'],
                    'credit_resolution': ['initial'],
                    'started_at__lt': ['2019-07-09 09:00:00'],
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


class AcceptOrRejectCheckFormTestCase(SimpleTestCase):
    """
    Tests related to the AcceptOrRejectCheckForm.
    """

    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens(),
            ),
        )

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_get_object(self, mock_get_need_attention_date):
        """
        Test that the form makes the right API call to get the object.
        """

        mock_get_need_attention_date.return_value = make_aware(datetime.datetime(2019, 7, 2, 9))

        check_id = 1
        check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'pending',
            'credit': {
                'started_at': '2020-01-19T10:45:13.529053Z',
            },
        }

        expected_check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'pending',
            'needs_attention': False,
        }

        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_data,
            )

            form = AcceptOrRejectCheckForm(
                object_id=check_id,
                request=self.request,
                data={
                    'fiu_action': 'accept',
                },
            )

            form_object = form.get_object()

            self.assertTrue(form.is_valid())
            self.assertFalse(form_object['needs_attention'])
            self.assertEqual(form_object['status'], expected_check_data['status'])

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_sets_needs_attention_true_if_within_time_delta(self, mock_get_need_attention_date):
        """
        Test that the form makes the right API call to get the object.
        """

        mock_get_need_attention_date.return_value = make_aware(datetime.datetime(2020, 1, 25, 9))

        check_id = 1
        check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'pending',
            'credit': {
                'started_at': '2020-01-19T03:45:13.529053Z',
            },
        }
        expected_check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'pending',
            'needs_attention': True,
            'credit': {
                'started_at': parse_datetime('2020-01-19T03:45:13.529053Z'),
            },
        }
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_data,
            )

            form = AcceptOrRejectCheckForm(
                object_id=check_id,
                request=self.request,
                data={
                    'fiu_action': 'accept',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertEqual(form.get_object(), expected_check_data)

    def test_accept(self):
        """
        Test that the form makes the right API call to accept the check.
        """
        check_id = 1
        check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'pending',
            'credit': {
                'started_at': '2020-01-19T03:45:13.529053Z',
            },
        }
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_data,
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/accept/'),
                status=204,
            )

            form = AcceptOrRejectCheckForm(
                object_id=check_id,
                request=self.request,
                data={
                    'fiu_action': 'accept',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertEqual(form.accept_or_reject(), (True, None))

    def test_form_invalid(self):
        """
        Test that if the check is not in pending, the form returns a validation error.
        """
        check_id = 1
        check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'rejected',
            'credit': {
                'started_at': '2020-01-19T03:45:13.529053Z',
            },
        }
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_data,
            )

            form = AcceptOrRejectCheckForm(
                object_id=check_id,
                request=self.request,
                data={
                    'fiu_action': 'accept',
                },
            )

            self.assertFalse(form.is_valid())
            self.assertEqual(
                form.errors,
                {'__all__': ["You cannot action this credit because it is not in 'pending'."]},
            )

    def test_accept_with_api_error(self):
        """
        Test that if the API return a non-2xx status code, the accept method returns False
        and the error is available in form.errors
        """
        check_id = 1
        check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'pending',
            'credit': {
                'started_at': '2020-01-19T03:45:13.529053Z',
            },
        }
        with responses.RequestsMock() as rsps, silence_logger():
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_data,
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/accept/'),
                status=400,
                json={'status': 'conflict'},
            )

            form = AcceptOrRejectCheckForm(
                object_id=check_id,
                request=self.request,
                data={
                    'fiu_action': 'accept',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertEqual(form.accept_or_reject(), (False, None))
            self.assertDictEqual(
                form.errors,
                {'__all__': ['There was an error with your request.']},
            )

    def test_reject(self):
        """
        Test that the form makes the right API call to reject the check.
        """
        check_id = 1
        check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'pending',
            'credit': {
                'started_at': '2020-01-19T03:45:13.529053Z',
            },
        }
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_data,
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/reject/'),
                status=204,
            )

            form = AcceptOrRejectCheckForm(
                object_id=check_id,
                request=self.request,
                data={
                    'payment_source_paying_multiple_prisoners': True,
                    'fiu_action': 'reject',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertEqual(form.accept_or_reject(), (True, None))

            last_request_body = json.loads(rsps.calls[-1].request.body)
            self.assertDictEqual(
                last_request_body,
                {
                    'decision_reason': '',
                    'rejection_reasons': {
                        'payment_source_paying_multiple_prisoners': True,
                    }
                }
            )

    def test_form_invalid_if_check_not_in_pending(self):
        """
        Test that if the check is not in pending, the form returns a validation error.
        """
        check_id = 1
        check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'accepted',
            'credit': {
                'started_at': '2020-01-19T03:45:13.529053Z',
            },
        }
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_data,
            )

            form = AcceptOrRejectCheckForm(
                object_id=check_id,
                request=self.request,
                data={
                    'decision_reason': 'reason',
                    'fiu_action': 'reject',
                },
            )

            self.assertFalse(form.is_valid())
            self.assertEqual(
                form.errors,
                {'__all__': ["You cannot action this credit because it is not in 'pending'."]},
            )

    def test_form_invalid_with_no_rejection_reason(self):
        """
        Test that if the rejection reason is not given, the form returns a validation error.
        """
        check_id = 1
        check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'pending',
            'credit': {
                'started_at': '2020-01-19T03:45:13.529053Z',
            },
        }
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_data,
            )
            form = AcceptOrRejectCheckForm(
                object_id=check_id,
                request=self.request,
                data={
                    'fiu_action': 'reject',
                },
            )

            self.assertFalse(form.is_valid())
            self.assertEqual(
                form.errors,
                {'__all__': ['You must provide a reason for rejecting a credit']}
            )

    def test_reject_with_api_error(self):
        """
        Test that if the API return a non-2xx status code, the accept method returns False
        and the error is available in form.errors
        """
        check_id = 1
        check_data = {
            'id': check_id,
            'description': ['Compliance check failed'],
            'status': 'pending',
            'credit': {
                'started_at': '2020-01-19T03:45:13.529053Z',
            },
        }
        with responses.RequestsMock() as rsps, silence_logger():
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_data,
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/reject/'),
                status=400,
                json={'status': 'conflict'},
            )

            form = AcceptOrRejectCheckForm(
                object_id=check_id,
                request=self.request,
                data={
                    'payment_source_paying_multiple_prisoners': True,
                    'fiu_action': 'reject',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertEqual(form.accept_or_reject(), (False, None))
            self.assertDictEqual(
                form.errors,
                {'__all__': ['There was an error with your request.']},
            )


class AssignCheckToUserFormTestCase(SimpleTestCase):
    """
    Tests related to the AssignCheckToUserForm.
    """

    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                pk=5,
                token=generate_tokens(),
            ),
        )

    def test_assign_or_unassign(self):
        """
        Test that the form makes the right API call to assign the check to a user list.
        """
        check_id = 1
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.PATCH,
                api_url(f'/security/checks/{check_id}/'),
                status=200,
                json={
                    'assigned_to': 5
                }
            )

            form = AssignCheckToUserForm(
                object_id=check_id,
                request=self.request,
                data={
                    'assignment': 'assign',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertEqual(form.assign_or_unassign(), True)

    def test_unassign(self):
        """
        Test that the form makes the right API call to unassign the check from a user list.
        """
        check_id = 1
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.PATCH,
                api_url(f'/security/checks/{check_id}/'),
                status=200,
                json={
                    'assigned_to': None
                }
            )

            form = AssignCheckToUserForm(
                object_id=check_id,
                request=self.request,
                data={
                    'assignment': 'unassign',
                },
            )

            self.assertTrue(form.is_valid())
            self.assertEqual(form.assign_or_unassign(), True)

    @mock.patch('django.contrib.messages.error')
    def test_form_returns_error_if_check_already_assigned_to_other_user(self, mock_messages_error):
        """
        Test that the form returns an error if check is assigned to another user.
        """
        check_id = 1
        with responses.RequestsMock() as rsps, silence_logger():
            rsps.add(
                rsps.PATCH,
                api_url(f'/security/checks/{check_id}/'),
                status=400
            )

            form = AssignCheckToUserForm(
                object_id=check_id,
                request=self.request,
                data={
                    'assignment': 'assign',
                },
            )

            form.is_valid()

            self.assertEqual(form.assign_or_unassign(), False)
            mock_messages_error.assert_called_with(
                self.request,
                _('Credit could not be added to your list.')
            )
