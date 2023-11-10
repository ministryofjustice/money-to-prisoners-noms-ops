import json
import unittest
from unittest import mock

from mtp_common.auth.test_utils import generate_tokens
import responses

from security.forms.review import ReviewCreditsForm
from security.tests import api_url


class ReviewCreditsFormTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens()
            )
        )

    def test_review_credits_form(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                api_url('/credits/'),
                json={
                    'count': 2,
                    'results': [
                        {
                            'id': 1,
                            'source': 'online',
                            'amount': 23000,
                            'intended_recipient': 'GEORGE MELLEY',
                            'prisoner_number': 'A1411AE', 'prisoner_name': 'GEORGE MELLEY',
                            'prison': 'LEI', 'prison_name': 'HMP LEEDS',
                            'sender_name': None, 'sender_email': 'HENRY MOORE',
                            'sender_sort_code': None, 'sender_account_number': None, 'sender_roll_number': None,
                            'resolution': 'pending',
                            'owner': None, 'owner_name': None,
                            'received_at': '2016-05-25T20:24:00Z', 'credited_at': None, 'refunded_at': None,
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
                            'resolution': 'pending',
                            'owner': None, 'owner_name': None,
                            'received_at': '2016-05-22T23:00:00Z', 'credited_at': None, 'refunded_at': None,
                        },
                    ]
                }
            )
            rsps.add(
                rsps.POST,
                api_url('/credits/comments/'),
            )

            form = ReviewCreditsForm(self.request, data={'comment_1': 'hold up'})
            self.assertTrue(form.is_valid())
            self.assertEqual(len(form.credits), 2)

            rsps.add(
                rsps.POST,
                api_url('/credits/actions/review/'),
            )
            form.review()
            self.assertEqual(
                json.loads(rsps.calls[-2].request.body.decode()),
                [{'credit': 1, 'comment': 'hold up'}]
            )
            self.assertEqual(
                json.loads(rsps.calls[-1].request.body.decode()),
                {'credit_ids': [1, 2]}
            )
