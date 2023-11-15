import copy
import datetime
import itertools
import json
import random
from unittest import mock
from urllib.parse import urlencode

from dateutil import parser
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from mtp_common.auth import urljoin
from mtp_common.test_utils import silence_logger
from parameterized import parameterized
import responses
from responses.matchers import json_params_matcher, query_param_matcher

from security import required_permissions
from security.constants import (
    SECURITY_FORMS_DEFAULT_PAGE_SIZE, CHECK_AUTO_ACCEPT_UNIQUE_CONSTRAINT_ERROR,
    CURRENT_CHECK_REJECTION_BOOL_CATEGORY_LABELS, CURRENT_CHECK_REJECTION_TEXT_CATEGORY_LABELS,
)
from security.tests import api_url
from security.tests.test_views import SecurityBaseTestCase
from security.views.check import AcceptOrRejectCheckView


def offset_isodatetime_by_ten_seconds(isodatetime, offset_multiplier=1):
    return (
        parse_datetime(isodatetime)
        + datetime.timedelta(seconds=offset_multiplier * 10)
    ).isoformat()


def generate_rejection_category_test_cases_text():
    return [
        (text_category, f'User-entered {text_category} text')
        for text_category in CURRENT_CHECK_REJECTION_TEXT_CATEGORY_LABELS
    ]


def generate_rejection_category_test_cases_bool():
    return [
        (text_category, True)
        for text_category in CURRENT_CHECK_REJECTION_BOOL_CATEGORY_LABELS
    ]


class BaseCheckViewTestCase(SecurityBaseTestCase):
    """
    Tests related to the check views.
    """
    sender_id = 2
    prisoner_id = 3
    credit_id = 5

    credit_created_date = timezone.localtime()

    SAMPLE_CHECK_BASE: dict = {
        'id': 1,
        'description': ['lorem ipsum'],
        'rules': ['RULE1', 'RULE2'],
        'status': 'pending',
        'actioned_at': None,
        'actioned_by': None,
        'assigned_to': 7,
        'auto_accept_rule_state': None,
    }

    SAMPLE_CREDIT_BASE: dict = {
        'id': 1,
        'amount': 1000,
        'card_expiry_date': '02/20',
        'card_number_first_digits': '123456',
        'card_number_last_digits': '9876',
        'prisoner_name': 'Jean Valjean',
        'prisoner_number': '24601',
        'sender_email': 'sender@example.com',
        'sender_name': 'MAISIE NOLAN',
        'source': 'online',
        'started_at': '2019-07-02T10:00:00Z',
        'received_at': None,
        'credited_at': None,
        'prisoner_profile': prisoner_id,
        'billing_address': {
            'debit_card_sender_details': 17
        },
    }

    SAMPLE_CHECK: dict = dict(SAMPLE_CHECK_BASE, credit=SAMPLE_CREDIT_BASE)

    SENDER_CREDIT: dict = dict(
        SAMPLE_CREDIT_BASE,
        security_check=SAMPLE_CHECK_BASE.copy(),
        intended_recipient='Mr G Melley',
        prisoner_name='Ms A. Nother Prisoner',
        prisoner_number='Number 6',
        amount=1000000,
        prison='LEI',
        prison_name='HMP LEEDS',
        billing_address={'line1': '102PF', 'city': 'London'},
        resolution='rejected',
        started_at=credit_created_date.isoformat(),
    )
    SENDER_CREDIT['security_check']['description'] = ['Strict compliance check failed']
    SENDER_CREDIT['security_check']['actioned_by_name'] = 'Javert'
    SENDER_CREDIT['security_check']['actioned_at'] = credit_created_date.isoformat()
    SENDER_CREDIT['security_check']['status'] = 'rejected'

    SENDER_CHECK: dict = copy.deepcopy(SAMPLE_CHECK)
    SENDER_CHECK['credit']['sender_profile'] = sender_id
    SENDER_CHECK['credit']['prisoner_profile'] = prisoner_id
    SENDER_CHECK['credit']['id'] = credit_id
    SENDER_CHECK['credit']['billing_address'] = {'debit_card_sender_details': 42}

    SENDER_CHECK_REJECTED: dict = dict(SENDER_CHECK, status='rejected')

    PRISONER_CREDIT: dict = dict(
        SAMPLE_CREDIT_BASE,
        security_check=SAMPLE_CHECK_BASE.copy(),
        amount=10,
        card_expiry_date='02/50',
        card_number_first_digits='01199988199',
        card_number_last_digits='7253',
        sender_email='someoneelse@example.com',
        sender_name='SOMEONE ELSE',
        prison='LEI',
        prison_name='HMP LEEDS',
        billing_address={'line1': 'Somewhere else', 'city': 'London'},
        resolution='credited',
    )
    PRISONER_CREDIT['security_check']['description'] = ['Soft compliance check failed']
    PRISONER_CREDIT['security_check']['actioned_at'] = credit_created_date.isoformat()
    PRISONER_CREDIT['security_check']['actioned_by_name'] = 'Staff'
    PRISONER_CREDIT['security_check']['status'] = 'accepted'

    required_checks_permissions = (
        *required_permissions,
        'security.view_check',
        'security.change_check',
    )

    def get_user_data(
        self,
        *args,
        permissions=required_checks_permissions,
        **kwargs,
    ):
        """
        Adds extra permissions to manage checks.
        """
        return super().get_user_data(*args, permissions=permissions, **kwargs)

    def mock_first_page_of_checks(self, rsps, count, *, only_mine=False):
        query_params = {
            # NB: must not overlap with mock_need_attention_count and mock_my_list_count
            'status': 'pending',
            'credit_resolution': 'initial',
            'offset': '0',
            'limit': '20',
        }
        if only_mine:
            query_params['assigned_to'] = self.mock_user_pk
        rsps.add(
            rsps.GET,
            api_url('/security/checks/'),
            match=[query_param_matcher(query_params, strict_match=True)],
            json={
                'count': count,
                'results': [self.SAMPLE_CHECK] * count,
            },
        )

    def mock_need_attention_count(self, rsps, need_attention_date: datetime.date, *, count=0, only_mine=False):
        query_params = {
            # NB: must not overlap with mock_my_list_count and mock_first_page_of_checks
            'status': 'pending',
            'credit_resolution': 'initial',
            'started_at__lt': need_attention_date.strftime('%Y-%m-%d %H:%M:%S'),
            'offset': '0',
            'limit': '1',
        }
        if only_mine:
            query_params['assigned_to'] = self.mock_user_pk
        rsps.add(
            rsps.GET,
            api_url('/security/checks/'),
            match=[query_param_matcher(query_params, strict_match=True)],
            json={
                'count': count,
                'results': [self.SAMPLE_CHECK] * count,
            }
        )

    def mock_my_list_count(self, rsps, count=0):
        query_params = {
            # NB: must not overlap with mock_need_attention_count and mock_first_page_of_checks
            'status': 'pending',
            'credit_resolution': 'initial',
            'assigned_to': self.mock_user_pk,
            'offset': '0',
            'limit': '1',
        }
        rsps.add(
            rsps.GET,
            api_url('/security/checks/'),
            match=[query_param_matcher(query_params, strict_match=True)],
            json={
                'count': count,
                'results': [self.SAMPLE_CHECK] * count,
            }
        )

    @classmethod
    def _get_prisoner_credit_list(cls, length):
        for i in range(length):
            yield dict(cls.PRISONER_CREDIT, id=i)

    @classmethod
    def _get_sender_credit_list(cls, length):
        for i in range(length):
            yield dict(cls.SENDER_CREDIT, id=i)

    @classmethod
    def _generate_auto_accept_response(cls, length, page_size, active=None, number_of_cardholder_names=1):
        return {
            'count': length,
            'prev': None,
            'next': None,
            'results': [
                {
                    'id': i,
                    'debit_card_sender_details': {
                        'card_number_last_digits': str(random.randint(1000, 9999)),
                        'cardholder_names': [
                            f'Cardholder Name {j}'
                            for j in range(number_of_cardholder_names)
                        ],
                        'id': random.randint(0, 5000),
                        'sender': random.randint(0, 5000),
                    },
                    'prisoner_profile': {
                        'id': random.randint(0, 5000),
                        'prisoner_name': f'Prisoner {i}',
                        'prisoner_number': 'A{}SB'.format(random.randint(1000, 9999)),
                    },
                    'states': [
                        {
                            'added_by': {
                                'first_name': f'First name {i}',
                                'last_name': f'Last Name {i}'
                            },
                            'active': not j,
                            'reason': f'I am an automatically generated auto-accept number {i}',
                            'created': (
                                timezone.localtime() - datetime.timedelta(hours=(5 - j))
                            ).isoformat(),
                            'auto_accept_rule': i
                        } for j in cls._generate_auto_accept_state_range(active)
                    ]
                }
                for i in range(page_size)
            ]
        }

    @staticmethod
    def _generate_auto_accept_state_range(active):
        if active is None:
            return range(random.randint(1, 5))
        if active is True:
            return [0]
        if active is False:
            return [0, 1]


class CheckListViewTestCase(BaseCheckViewTestCase):
    """
    Tests related to CheckListView.
    """

    def test_cannot_access_view(self):
        """
        Test that if the logged in user doesn't have the right permissions, he/she
        gets redirected to the dashboard.
        """
        user_data = self.get_user_data(permissions=required_permissions)
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps, user_data=user_data)
            response = self.client.get(reverse('security:check_list'), follow=True)
            self.assertRedirects(response, reverse('security:dashboard'))

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_view(self, mock_get_need_attention_date):
        """
        Test that the view displays the pending checks returned by the API.
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 2, 9))

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_first_page_of_checks(rsps, 1)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value)
            self.mock_my_list_count(rsps)

            response = self.client.get(reverse('security:check_list'), follow=True)
            self.assertContains(response, '123456******9876')
            self.assertContains(response, '02/20')

            content = response.content.decode()
            self.assertIn('24601', content)
            self.assertIn('1 credit', content)
            self.assertIn('This credit does not need attention today', content)
            self.assertNotIn('credit needs attention', content)
            self.assertNotIn('credits need attention', content)

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_displays_count_of_credits_needing_attention(self, mock_get_need_attention_date):
        """
        Test that the view shows how many credits need attention.
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 9, 9))

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_first_page_of_checks(rsps, 2)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value, count=2)
            self.mock_my_list_count(rsps)

            response = self.client.get(reverse('security:check_list'), follow=True)
            self.assertContains(response, '123456******9876')
            self.assertContains(response, '02/20')

            content = response.content.decode()
            self.assertIn('2 credits need attention', content)
            self.assertIn('This credit needs attention today!', content)

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_credit_row_has_review_link(self, mock_get_need_attention_date):
        """
        Test that the view displays link to review a credit.
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 2, 9))

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_first_page_of_checks(rsps, 1)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value, count=2)
            self.mock_my_list_count(rsps)

            response = self.client.get(reverse('security:check_list'), follow=True)

            self.assertContains(response, 'Review <span class="govuk-visually-hidden">credit to Jean Valjean</span>')


class MyCheckListViewTestCase(BaseCheckViewTestCase):
    """
    Tests related to CheckListView.
    """

    def test_cannot_access_view(self):
        """
        Test that if the logged in user doesn't have the right permissions, he/she
        gets redirected to the dashboard.
        """
        user_data = self.get_user_data(permissions=required_permissions)
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps, user_data=user_data)
            response = self.client.get(reverse('security:my_check_list'), follow=True)
            self.assertRedirects(response, reverse('security:dashboard'))

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_view(self, mock_get_need_attention_date):
        """
        Test that the view displays the pending checks returned by the API.
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 2, 9))

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_first_page_of_checks(rsps, 1, only_mine=True)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value, only_mine=True)
            self.mock_my_list_count(rsps, 1)

            response = self.client.get(reverse('security:my_check_list'), follow=True)
            self.assertContains(response, '123456******9876')
            self.assertContains(response, '02/20')

            content = response.content.decode()
            self.assertIn('24601', content)
            self.assertIn('1 credit', content)
            self.assertIn('This credit does not need attention today', content)
            self.assertNotIn('credit needs attention', content)
            self.assertNotIn('credits need attention', content)
            self.assertIn('My list (1)', content)

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_displays_count_of_credits_needing_attention(self, mock_get_need_attention_date):
        """
        Test that the view shows how many credits need attention.
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 9, 9))

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_first_page_of_checks(rsps, 2, only_mine=True)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value, count=2, only_mine=True)
            self.mock_my_list_count(rsps, 2)

            response = self.client.get(reverse('security:my_check_list'), follow=True)
            self.assertContains(response, '123456******9876')
            self.assertContains(response, '02/20')

            content = response.content.decode()
            self.assertIn('2 credits need attention', content)
            self.assertIn('This credit needs attention today!', content)

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_credit_row_has_review_link(self, mock_get_need_attention_date):
        """
        Test that the view displays link to review a credit.
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 2, 9))

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_first_page_of_checks(rsps, 1, only_mine=True)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value, only_mine=True)
            self.mock_my_list_count(rsps, 1)

            response = self.client.get(reverse('security:my_check_list'), follow=True)

            self.assertContains(response, 'Review <span class="govuk-visually-hidden">credit to Jean Valjean</span>')


class CheckHistoryListViewTestCase(BaseCheckViewTestCase):
    """
    Tests related to CheckHistoryListView.
    """
    SAMPLE_CHECK_WITH_ACTIONED_BY: dict = dict(
        BaseCheckViewTestCase.SAMPLE_CHECK,
        actioned_at='2020-01-13 12:00:00+00',
        actioned_by=1,
        decision_reason='Money issues',
        actioned_by_name='Barry Garlow',
        status='accepted',
    )

    SAMPLE_CHECK_WITH_ACTIONED_BY['credit'].update(
        billing_address={
            'id': 21,
            'line1': 'Studio 33',
            'line2': 'Allen port',
            'city': 'Gloverside',
            'country': 'UK',
            'postcode': 'S1 3HS',
            'debit_card_sender_details': 17
        },
        prison_name='Brixton Prison',
        prisoner_number='24601',
    )

    def test_cannot_access_view(self):
        """
        Test that if the logged in user doesn't have the right permissions, he/she
        gets redirected to the dashboard.
        """
        user_data = self.get_user_data(permissions=required_permissions)
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps, user_data=user_data)
            response = self.client.get(reverse('security:check_history'), follow=True)
            self.assertRedirects(response, reverse('security:dashboard'))

    def test_view(self):
        """
        Test that the view displays the history of checks caught by delayed capture by the API.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/security/checks/?{querystring}'.format(
                        querystring=urlencode([
                            ('started_at__gte', '2020-01-02T12:00:00'),
                            ('actioned_by', True),
                            ('offset', 0),
                            ('limit', 20),
                            ('ordering', '-created'),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [self.SAMPLE_CHECK_WITH_ACTIONED_BY],
                },
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/security/checks/?{querystring}'.format(
                        querystring=urlencode([
                            ('status', 'pending'),
                            ('credit_resolution', 'initial'),
                            ('assigned_to', 5),
                            ('offset', 0),
                            ('limit', 1),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 2,
                    'results': [self.SAMPLE_CHECK_WITH_ACTIONED_BY, self.SAMPLE_CHECK_WITH_ACTIONED_BY],
                }
            )

            response = self.client.get(reverse('security:check_history'))

        self.assertContains(response, '123456******9876')
        self.assertContains(response, '02/20')

        content = response.content.decode()

        self.assertIn('24601', content)
        self.assertIn('1 credit', content)
        self.assertIn('My list (2)', content)

    def test_view_contains_relevant_data(self):
        """
        Test that the view displays the correct data from the API.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url('/security/checks/'),
                json={
                    'count': 1,
                    'results': [self.SAMPLE_CHECK_WITH_ACTIONED_BY],
                },
            )
            response = self.client.get(reverse('security:check_history'))

        self.assertContains(response, '123456******9876')
        self.assertContains(response, '02/20')
        self.assertContains(response, 'Barry Garlow')
        self.assertContains(response, 'Money issues')
        self.assertContains(response, 'S1 3HS')
        self.assertContains(response, '24601')
        self.assertContains(response, 'Accepted')
        self.assertContains(response, 'Brixton Prison')
        self.assertContains(response, 'Decision details:')

    def test_view_does_not_display_decision_if_none(self):
        """
        Test that the view displays the correct data from the API.
        """
        self.SAMPLE_CHECK_WITH_ACTIONED_BY['decision_reason'] = None

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url('/security/checks/'),
                json={
                    'count': 1,
                    'results': [self.SAMPLE_CHECK_WITH_ACTIONED_BY],
                },
            )
            response = self.client.get(reverse('security:check_history'))

        self.assertContains(response, 'No decision reason entered')

    @parameterized.expand(
        CURRENT_CHECK_REJECTION_BOOL_CATEGORY_LABELS.items()
    )
    def test_credit_history_row_has_reason_checkbox_populated(
        self, rejection_reason_key, rejection_reason_full
    ):
        """
        Test that the view displays checkboxes associated with a credit.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/security/checks/?{querystring}'.format(
                        querystring=urlencode([
                            ('started_at__gte', '2020-01-02T12:00:00'),
                            ('actioned_by', True),
                            ('offset', 0),
                            ('limit', 20),
                            ('ordering', '-created'),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [
                        dict(
                            self.SENDER_CHECK_REJECTED,
                            rejection_reasons={rejection_reason_key: True}
                        )
                    ]
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/security/checks/?{querystring}'.format(
                        querystring=urlencode([
                            ('status', 'pending'),
                            ('credit_resolution', 'initial'),
                            ('assigned_to', 5),
                            ('offset', 0),
                            ('limit', 1),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 2,
                    'results': [self.SAMPLE_CHECK_WITH_ACTIONED_BY, self.SAMPLE_CHECK_WITH_ACTIONED_BY],
                }
            )

            response = self.client.get(reverse('security:check_history'))

        self.assertContains(response, rejection_reason_full)

    @parameterized.expand(
        generate_rejection_category_test_cases_text()
    )
    def test_credit_history_row_has_string_reason_populated(
        self, rejection_reason_key, rejection_reason_value
    ):
        """
        Test that the view displays the reason for associated populated checkboxes with a credit.
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/security/checks/?{querystring}'.format(
                        querystring=urlencode([
                            ('started_at__gte', '2020-01-02T12:00:00'),
                            ('actioned_by', True),
                            ('offset', 0),
                            ('limit', 20),
                            ('ordering', '-created'),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [
                        dict(
                            self.SENDER_CHECK_REJECTED,
                            rejection_reasons={rejection_reason_key: rejection_reason_value}
                        )
                    ]
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/security/checks/?{querystring}'.format(
                        querystring=urlencode([
                            ('status', 'pending'),
                            ('credit_resolution', 'initial'),
                            ('assigned_to', 5),
                            ('offset', 0),
                            ('limit', 1),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 2,
                    'results': [self.SAMPLE_CHECK_WITH_ACTIONED_BY, self.SAMPLE_CHECK_WITH_ACTIONED_BY],
                }
            )

            response = self.client.get(reverse('security:check_history'))

        self.assertContains(response, rejection_reason_value)

    def test_view_shows_removed_rejection_reason_descriptions(self):
        """
        Test that rejection reasons which are no longer used are still displayable in history
        """
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/security/checks/?{querystring}'.format(
                        querystring=urlencode([
                            ('started_at__gte', '2020-01-02T12:00:00'),
                            ('actioned_by', True),
                            ('offset', 0),
                            ('limit', 20),
                            ('ordering', '-created'),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [
                        dict(
                            self.SENDER_CHECK_REJECTED,
                            rejection_reasons={'fiu_investigation_id': 'ABC123000ABC'}
                        )
                    ]
                }
            )
            self.mock_my_list_count(rsps, 0)

            response = self.client.get(reverse('security:check_history'))

        self.assertContains(response, 'Associated FIU investigation')
        self.assertContains(response, 'ABC123000ABC')

    def test_view_includes_matching_credit_history_including_active_auto_accept(self):
        """
        Test that the view displays auto-accepted credits related by sender id to the credit subject to a check.
        """
        check_to_return = dict(
            self.SENDER_CHECK,
            status='accepted',
            auto_accept_rule_state={
                'added_by': {
                    'username': 'security-fiu-0',
                    'first_name': 'Security FIU',
                    'last_name': 'Staff'
                },
                'active': True,
                'reason': 'I am an automatically generated auto-accept inactive state number 0',
                'created': '2021-02-28T20:53:40.131236Z',
                'auto_accept_rule': 651
            }
        )
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/security/checks/?{querystring}'.format(
                        querystring=urlencode([
                            ('ordering', '-created'),
                            ('actioned_by', True),
                            ('started_at__gte', '2020-01-02T12:00:00'),
                            ('offset', 0),
                            ('limit', 20),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [check_to_return]
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/security/checks/?{querystring}'.format(
                        querystring=urlencode([
                            ('status', 'pending'),
                            ('credit_resolution', 'initial'),
                            ('assigned_to', 5),
                            ('offset', 0),
                            ('limit', 1),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [check_to_return],
                }
            )
            response = self.client.get(
                reverse(
                    'security:check_history',
                ),
            )
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)

        self.assertIn('Auto accepted', response_content)
        self.assertIn('123456******9876', response_content)
        self.assertIn('02/20', response_content)
        self.assertIn('MAISIE NOLAN', response_content)
        self.assertIn('£10.00', response_content)
        self.assertIn('Jean Valjean', response_content)
        self.assertIn(
            'Reason for automatically accepting:',
            response_content
        )
        self.assertIn(
            'I am an automatically generated auto-accept inactive state number 0',
            response_content
        )


class AcceptOrRejectCheckViewTestCase(BaseCheckViewTestCase):
    """
    Tests related to AcceptOrRejectCheckView.
    """

    def test_cannot_access_view(self):
        """
        Test that if the logged in user doesn't have the right permissions, he/she
        gets redirected to the dashboard.
        """
        user_data = self.get_user_data(permissions=required_permissions)
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps, user_data=user_data)
            url = reverse('security:resolve_check', kwargs={'check_id': 1})
            response = self.client.get(url, follow=True)
            self.assertRedirects(response, reverse('security:dashboard'))

    def test_get(self):
        """
        Test that the view displays the pending check returned by the API.
        """
        response_len = 4
        check_id = 1
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_prisoner_credit_list(response_len))
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.get(url, follow=True)

            self.assertContains(response, 'Accept credit')
            self.assertContains(response, '123456******9876')
            self.assertContains(response, '02/20')

    def test_get_with_previous_unbound_active_auto_accept(self):
        """
        Test that the view renders the form without auto-accept form
        """
        response_len = 4
        check_id = 1
        reason = 'Prisoners mother'
        different_user_data = self.get_user_data(first_name='different', last_name='user')
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_prisoner_credit_list(response_len))
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 1, 'prev': None, 'next': None, 'results': [{
                    'debit_card_sender_details': self.SENDER_CHECK['credit']['billing_address'][
                        'debit_card_sender_details'
                    ],
                    'prisoner_profile': self.SENDER_CHECK['credit']['prisoner_profile'],
                    'states': [
                        {
                            'created': (
                                timezone.localtime() - datetime.timedelta(hours=3)
                            ).isoformat(),
                            'active': True
                        },
                        {
                            'created': (
                                timezone.localtime() - datetime.timedelta(hours=2)
                            ).isoformat(),
                            'active': False
                        },
                        {
                            'created': (
                                timezone.localtime() - datetime.timedelta(hours=1)
                            ).isoformat(),
                            'active': True,
                            'reason': reason,
                            'added_by': {
                                'first_name': different_user_data['first_name'],
                                'last_name': different_user_data['last_name'],
                            }
                        },
                    ]
                }]}
            )

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.get(url, follow=True)

            self.assertContains(response, 'Accept credit')
            self.assertContains(response, '123456******9876')
            self.assertContains(response, '02/20')
            self.assertNotContains(response, 'Automatically accept future credits from')
            self.assertContains(
                response,
                f'Auto accept started for credits from {self.SENDER_CHECK["credit"]["sender_name"]} to '
                f'{self.SENDER_CHECK["credit"]["prisoner_number"]}'
            )
            self.assertContains(response, 'Started by:')
            self.assertContains(response, f'{different_user_data["first_name"]} {different_user_data["last_name"]}')
            self.assertContains(response, 'Date:')
            self.assertContains(
                response,
                (
                    timezone.localtime() - datetime.timedelta(hours=1)
                ).strftime('%d/%m/%Y %H:%M')
            )
            self.assertContains(response, 'Reason for automatically accepting:')
            self.assertContains(response, reason)

    def test_get_with_previous_unbound_inactive_auto_accept(self):
        """
        Test that the view renders the form with auto-accept form
        """
        response_len = 4
        check_id = 1
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_prisoner_credit_list(response_len))
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 1, 'prev': None, 'next': None, 'results': [{
                    'debit_card_sender_details': self.SENDER_CHECK['credit']['billing_address'][
                        'debit_card_sender_details'
                    ],
                    'prisoner_profile': self.SENDER_CHECK['credit']['prisoner_profile'],
                    'states': [
                        {
                            'created': (timezone.localtime() - datetime.timedelta(hours=2)).isoformat(),
                            'active': True
                        },
                        {
                            'created': (timezone.localtime() - datetime.timedelta(hours=1)).isoformat(),
                            'active': False
                        },
                    ]
                }]}
            )

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.get(url, follow=True)

            self.assertContains(response, 'Accept credit')
            self.assertContains(response, '123456******9876')
            self.assertContains(response, '02/20')
            self.assertContains(response, 'Automatically accept future credits from')
            self.assertNotContains(
                response,
                f'Auto accept started for credits from {self.SENDER_CHECK["credit"]["sender_name"]} to '
                f'{self.SENDER_CHECK["credit"]["prisoner_number"]}'
            )

    def test_check_view_hides_action_buttons_if_resolved_already(self):
        """
        There is currently nothing to prevent the view from showing a resolved security check.
        Test that the accept/reject form is absent for resolved checks.
        NB: as this test is not concerned with the api being called with the right parameters, the responses mock
            does not force the query string to be correct unlike other tests.
        """
        response_len = 0
        check_id = 1
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK_REJECTED
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/'.format(
                        sender_profile_id=self.sender_id,
                    ),
                ),
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/'.format(
                        prisoner_profile_id=self.prisoner_id,
                    ),
                ),
                json={
                    'count': response_len,
                    'results': list(self._get_prisoner_credit_list(response_len))
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.get(url)
        content = response.content.decode()
        self.assertNotIn('name="fiu_action"', content, msg='Action button exists on page')
        self.assertIn('This credit was rejected by', content)

    def test_check_view_includes_matching_credit_history(self):
        """
        Test that the view displays credits related by sender id to the credit subject to a check.
        """
        check_id = 1
        response_len = 4
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len))
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_prisoner_credit_list(response_len))
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            response = self.client.get(
                reverse(
                    'security:resolve_check',
                    kwargs={'check_id': check_id},
                ),
            )
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('123456******9876', response_content)
        self.assertIn('02/20', response_content)
        self.assertIn('Jean Valjean', response_content)
        self.assertIn('£10.00', response_content)

        # Senders previous credit
        self.assertIn('Ms A. Nother Prisoner', response_content)
        self.assertIn('£10,000.00', response_content)
        self.assertIn('Strict compliance check failed', response_content)
        self.assertIn('Javert', response_content)

        # Prisoners previous credit
        self.assertIn('£0.10', response_content)
        self.assertIn('01199988199******7253', response_content)
        self.assertIn('02/50', response_content)
        self.assertIn('SOMEONE ELSE', response_content)
        self.assertIn('Number 6', response_content)
        self.assertIn('Soft compliance check failed', response_content)
        self.assertIn('Staff', response_content)

        # TODO add in assertion for ordering

    def test_check_view_includes_matching_credit_history_including_active_auto_accept(self):
        """
        Test that the view displays auto-accepted credits related by sender id to the credit subject to a check.
        """
        check_id = 1
        response_len = 2
        sender_active_auto_accept_rule_state = {
            'active': True,
            'reason': 'I should be here sender'
        }
        sender_inactive_auto_accept_rule_state = {
            'active': False,
            'reason': 'I shouldnt be here sender'
        }
        prisoner_active_auto_accept_rule_state = {
            'active': True,
            'reason': 'I should be here prisoner'
        }
        prisoner_inactive_auto_accept_rule_state = {
            'active': False,
            'reason': 'I shouldnt be here prisoner'
        }
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 2,
                    'results': [
                        dict(
                            self.SENDER_CREDIT,
                            id=0,
                            security_check=dict(
                                self.PRISONER_CREDIT['security_check'],
                                auto_accept_rule_state=sender_active_auto_accept_rule_state
                            )
                        ),
                        dict(
                            self.SENDER_CREDIT,
                            id=1,
                            security_check=dict(
                                self.SENDER_CREDIT['security_check'],
                                auto_accept_rule_state=sender_inactive_auto_accept_rule_state
                            )
                        )
                    ]
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 2,
                    'results': [
                        dict(
                            self.PRISONER_CREDIT,
                            id=0,
                            security_check=dict(
                                self.PRISONER_CREDIT['security_check'],
                                auto_accept_rule_state=prisoner_active_auto_accept_rule_state
                            )
                        ),
                        dict(
                            self.PRISONER_CREDIT,
                            id=1,
                            security_check=dict(
                                self.PRISONER_CREDIT['security_check'],
                                auto_accept_rule_state=prisoner_inactive_auto_accept_rule_state
                            )
                        )
                    ]
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            response = self.client.get(
                reverse(
                    'security:resolve_check',
                    kwargs={'check_id': check_id},
                ),
            )
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode(response.charset)
        self.assertIn('123456******9876', response_content)
        self.assertIn('02/20', response_content)
        self.assertIn('Jean Valjean', response_content)
        self.assertIn('£10.00', response_content)

        # Senders previous credit
        self.assertIn('Ms A. Nother Prisoner', response_content)
        self.assertIn('£10,000.00', response_content)
        self.assertIn('Strict compliance check failed', response_content)
        self.assertIn('Javert', response_content)
        self.assertIn(
            'Reason for automatically accepting:',
            response_content
        )
        self.assertIn(
            sender_active_auto_accept_rule_state['reason'],
            response_content
        )
        self.assertNotIn(
            sender_inactive_auto_accept_rule_state['reason'],
            response_content
        )

        # Prisoners previous credit
        self.assertIn('£0.10', response_content)
        self.assertIn('01199988199******7253', response_content)
        self.assertIn('02/50', response_content)
        self.assertIn('SOMEONE ELSE', response_content)
        self.assertIn('Number 6', response_content)
        self.assertIn('Soft compliance check failed', response_content)
        self.assertIn(
            prisoner_active_auto_accept_rule_state['reason'],
            response_content
        )
        self.assertNotIn(
            prisoner_inactive_auto_accept_rule_state['reason'],
            response_content
        )

    @parameterized.expand(
        CURRENT_CHECK_REJECTION_BOOL_CATEGORY_LABELS.items()
    )
    def test_credit_history_row_has_reason_checkbox_populated_for_prisoner_check(
        self, rejection_reason_key, rejection_reason_full
    ):
        """
        Test that the view displays checkboxes associated with a credit.
        """
        check_id = 1
        response_len = 4
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [
                        dict(
                            self.PRISONER_CREDIT,
                            security_check=dict(
                                self.PRISONER_CREDIT['security_check'],
                                rejection_reasons={rejection_reason_key: True}
                            )
                        )
                    ],
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            response = self.client.get(
                reverse(
                    'security:resolve_check',
                    kwargs={'check_id': check_id},
                ),
            )

            self.assertContains(response, rejection_reason_full)

    @parameterized.expand(
        CURRENT_CHECK_REJECTION_BOOL_CATEGORY_LABELS.items()
    )
    def test_credit_history_row_has_reason_checkbox_populated_for_sender_check(
        self, rejection_reason_key, rejection_reason_full
    ):
        """
        Test that the view displays checkboxes associated with a credit.
        """
        check_id = 1
        response_len = 2
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            sender_credit_response = dict(
                self.SENDER_CREDIT,
                id=self.credit_id + 1,
                security_check=dict(
                    self.SENDER_CREDIT['security_check'],
                    rejection_reasons={rejection_reason_key: True}
                )
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [
                        sender_credit_response
                    ]
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', f'{self.credit_id},{sender_credit_response["id"]}'),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_prisoner_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            response = self.client.get(
                reverse(
                    'security:resolve_check',
                    kwargs={'check_id': check_id},
                ),
            )

            self.assertContains(response, rejection_reason_full)

    @parameterized.expand(
        generate_rejection_category_test_cases_text()
    )
    def test_credit_history_row_has_string_reason_populated_for_prisoner_check(
        self, rejection_reason_key, rejection_reason_value
    ):
        """
        Test that the view displays the reason for associated populated checkboxes with a credit.
        """
        check_id = 1
        response_len = 2
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [
                        dict(
                            self.PRISONER_CREDIT,
                            security_check=dict(
                                self.PRISONER_CREDIT['security_check'],
                                rejection_reasons={rejection_reason_key: rejection_reason_value}
                            )
                        )
                    ]
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            response = self.client.get(
                reverse(
                    'security:resolve_check',
                    kwargs={'check_id': check_id},
                ),
            )

            self.assertContains(response, rejection_reason_value)

    @parameterized.expand(
        generate_rejection_category_test_cases_text()
    )
    def test_credit_history_row_has_string_reason_populated_for_sender_check(
        self, rejection_reason_key, rejection_reason_value
    ):
        """
        Test that the view displays the reason for associated populated checkboxes with a credit.
        """
        check_id = 1
        response_len = 2
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            sender_credit_response = dict(
                self.SENDER_CREDIT,
                id=self.credit_id + 1,
                security_check=dict(
                    self.SENDER_CREDIT['security_check'],
                    rejection_reasons={rejection_reason_key: rejection_reason_value}
                )
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 1,
                    'results': [
                        sender_credit_response,
                    ]
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', f'{self.credit_id},{sender_credit_response["id"]}'),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            response = self.client.get(
                reverse(
                    'security:resolve_check',
                    kwargs={'check_id': check_id},
                ),
            )

            self.assertContains(response, rejection_reason_value)

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_accept_check(self, mock_get_need_attention_date):
        """
        Test that if one tries to accept pending check, check marked as accepted
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 9, 9))

        check_id = 1
        payload_values = {
            'decision_reason': '',
        }
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/accept/'),
                match=[
                    json_params_matcher(payload_values)
                ],
                status=204,
            )
            # for checks list after redirect:
            self.mock_first_page_of_checks(rsps, 0)
            self.mock_my_list_count(rsps)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value)

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.post(
                url,
                data={
                    'fiu_action': 'accept',
                },
                follow=True
            )

            self.assertRedirects(response, reverse('security:check_list'))
            self.assertContains(response, 'Credit accepted')

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_accept_check_without_reactivating_auto_accept(self, mock_get_need_attention_date):
        """
        Test that if one tries to accept pending check, check marked as accepted, without reactivating auto_accept

        We implicitly assert that no API call is made to the security/check/auto-accept endpoint even if
        check.auto_accept_rule populated
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 9, 9))

        check_id = 1
        auto_accept_rule_id = 35
        payload_values = {
            'decision_reason': '',
        }
        check_with_inactive_auto_accept = copy.deepcopy(self.SENDER_CHECK)
        check_with_inactive_auto_accept['auto_accept_rule_state'] = {
            'auto_accept_rule': auto_accept_rule_id,
        }
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_with_inactive_auto_accept
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/accept/'),
                match=[
                    json_params_matcher(payload_values)
                ],
                status=204,
            )
            # for checks list after redirect:
            self.mock_first_page_of_checks(rsps, 0)
            self.mock_my_list_count(rsps)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value)

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.post(
                url,
                data={
                    'fiu_action': 'accept',
                },
                follow=True
            )

            self.assertRedirects(response, reverse('security:check_list'))
            self.assertContains(response, 'Credit accepted')

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_accept_check_with_auto_accept(self, mock_get_need_attention_date):
        """
        Test that if one tries to accept pending check, check marked as accepted, and auto accept added in active state

        We assert that API call is made to POST security/check/auto-accept endpoint if cleaned_data.auto_accept_reason
        populated
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 9, 9))

        check_id = 1
        payload_values = {
            'decision_reason': '',
        }
        auto_accept_payload_values = {
            'prisoner_profile_id': self.SENDER_CHECK['credit']['prisoner_profile'],
            'debit_card_sender_details_id': self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details'],
            'states': [{
                'reason': 'cause I said so'
            }]
        }
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/accept/'),
                match=[
                    json_params_matcher(payload_values)
                ],
                status=204,
            )
            rsps.add(
                rsps.POST,
                api_url('/security/checks/auto-accept'),
                match=[
                    json_params_matcher(auto_accept_payload_values)
                ],
                status=201
            )
            # for checks list after redirect:
            self.mock_first_page_of_checks(rsps, 0)
            self.mock_my_list_count(rsps)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value)

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.post(
                url,
                data={
                    'fiu_action': 'accept',
                    'auto_accept_reason': 'cause I said so'
                },
                follow=True
            )

            self.assertRedirects(response, reverse('security:check_list'))
            self.assertContains(response, 'Credit accepted')

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_accept_check_with_auto_accept_integrity_error(self, mock_get_need_attention_date):
        """
        Test that if one tries to accept pending check, check marked as accepted, info message displayed

        We assert that API call is made to POST security/check/auto-accept endpoint if cleaned_data.auto_accept_reason
        populated
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 9, 9))

        check_id = 1
        payload_values = {
            'decision_reason': '',
        }
        auto_accept_payload_values = {
            'prisoner_profile_id': self.SENDER_CHECK['credit']['prisoner_profile'],
            'debit_card_sender_details_id': self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details'],
            'states': [{
                'reason': 'cause I said so'
            }]
        }
        check_get_api_url = api_url(f'/security/checks/{check_id}/')
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                check_get_api_url,
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/accept/'),
                match=[
                    json_params_matcher(payload_values)
                ],
                status=204,
            )
            rsps.add(
                rsps.POST,
                api_url('/security/checks/auto-accept'),
                match=[
                    json_params_matcher(auto_accept_payload_values)
                ],
                status=400,
                json={
                    'non_field_errors': [
                        CHECK_AUTO_ACCEPT_UNIQUE_CONSTRAINT_ERROR
                    ]
                }
            )
            # for checks list after redirect:
            self.mock_first_page_of_checks(rsps, 0)
            self.mock_my_list_count(rsps)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value)

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.post(
                url,
                data={
                    'fiu_action': 'accept',
                    'auto_accept_reason': 'cause I said so'
                },
                follow=True
            )

            self.assertRedirects(response, reverse('security:check_list'))
            self.assertContains(response, 'Credit accepted')
            self.assertContains(
                response,
                (
                    'The auto-accept could not be created because one '
                    'already exists for {sender_name} and {prisoner_number}'.format(
                        sender_name=self.SENDER_CHECK['credit']['sender_name'],
                        prisoner_number=self.SENDER_CHECK['credit']['prisoner_number']
                    )
                )
            )

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_accept_check_when_reactivating_auto_accept(self, mock_get_need_attention_date):
        """
        Test that if one tries to accept pending check, check marked as accepted, and auto accept reactivated

        We assert that API call is made to PATCH security/check/auto-accept endpoint if cleaned_data.auto_accept_reason
        and check.auto_accept_rule populated
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 9, 9))

        check_id = 1
        auto_accept_rule_id = 35
        payload_values = {
            'decision_reason': '',
        }
        check_with_inactive_auto_accept = copy.deepcopy(self.SENDER_CHECK)
        check_with_inactive_auto_accept['auto_accept_rule_state'] = {
            'auto_accept_rule': auto_accept_rule_id,
        }
        auto_accept_payload_values = {
            'states': [{
                'active': True,
                'reason': 'cause I said so'
            }]
        }
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=check_with_inactive_auto_accept
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/accept/'),
                match=[
                    json_params_matcher(payload_values)
                ],
                status=201,
            )
            rsps.add(
                rsps.PATCH,
                api_url(f'/security/checks/auto-accept/{auto_accept_rule_id}'),
                match=[
                    json_params_matcher(auto_accept_payload_values)
                ],
                status=200,
            )
            # for checks list after redirect:
            self.mock_first_page_of_checks(rsps, 0)
            self.mock_my_list_count(rsps)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value)

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.post(
                url,
                data={
                    'fiu_action': 'accept',
                    'auto_accept_reason': 'cause I said so'
                },
                follow=True
            )

            self.assertRedirects(response, reverse('security:check_list'))
            self.assertContains(response, 'Credit accepted')

    @parameterized.expand(
        generate_rejection_category_test_cases_text() + generate_rejection_category_test_cases_bool()
    )
    @mock.patch('security.forms.check.get_need_attention_date')
    def test_reject_check(self, rejection_field_key, rejection_field_value, mock_get_need_attention_date):
        """
        Test that if a pending check is rejected, the view redirects to the list of checks
        and a successful message is displayed.
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 9, 9))

        check_id = 1
        payload_values = {
            'decision_reason': 'iamfurtherdetails',
            'rejection_reasons': {rejection_field_key: rejection_field_value}
        }
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.POST,
                api_url(f'/security/checks/{check_id}/reject/'),
                match=[
                    json_params_matcher(payload_values)
                ],
                status=204,
            )
            # for checks list after redirect:
            self.mock_first_page_of_checks(rsps, 0)
            self.mock_my_list_count(rsps)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value)

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.post(
                url,
                data={
                    'reject_further_details': 'iamfurtherdetails',
                    rejection_field_key: rejection_field_value,
                    'fiu_action': 'reject',
                },
                follow=True,
            )

            self.assertRedirects(response, reverse('security:check_list'))
            self.assertContains(response, 'Credit rejected')

    def test_invalid_if_check_not_in_pending(self):
        """
        Test that if one tries to reject an already accepted check, a validation error is displayed.
        """
        check_id = 1
        response_len = 4
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK_REJECTED
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len))
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_prisoner_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.post(
                url,
                data={
                    'payment_source_paying_multiple_prisoners': True,
                    'fiu_action': 'reject',
                },
                follow=True,
            )

            self.assertContains(response, 'You cannot action this credit')

    def test_invalid_with_no_rejection_reason(self):
        """
        Test that if the rejection reason is not given, a validation error is displayed.
        """
        check_id = 1
        response_len = 2
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_sender_credit_list(response_len)),
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': response_len,
                    'results': list(self._get_prisoner_credit_list(response_len))
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})
            response = self.client.post(
                url,
                data={
                    'fiu_action': 'reject',
                },
                follow=True,
            )

            self.assertContains(response, 'You must provide a reason for rejecting a credit')

    def test_credit_history_ordering(self):
        """
        Test that the credit history is correctly ordered by `started_at`
        """
        sender_credits = [
            dict(
                self.SENDER_CREDIT,
                id=i,
                security_check=dict(
                    self.SENDER_CREDIT['security_check'],
                    actioned_at=offset_isodatetime_by_ten_seconds(
                        self.SENDER_CREDIT['security_check']['actioned_at'], i
                    )
                )
            )
            for i in range(4)
        ]
        prisoner_credits = [
            dict(
                self.PRISONER_CREDIT,
                id=i,
                security_check=dict(
                    self.PRISONER_CREDIT['security_check'],
                    actioned_at=offset_isodatetime_by_ten_seconds(
                        self.PRISONER_CREDIT['security_check']['actioned_at'], i
                    )
                )
            )
            for i in range(4)
        ]
        # We expect the credits to be ordered according to started at.
        # Given the offsets above we expect the first sender credit followed by the first prisoner credit
        # and so on
        expected_related_credits = list(itertools.chain(*zip(sender_credits, prisoner_credits)))
        # We want to display the newest credits first
        expected_related_credits.reverse()
        mock_api_session = mock.MagicMock()
        mock_api_session.get().json.side_effect = [
            {'results': sender_credits, 'count': len(sender_credits)},
            {'results': prisoner_credits, 'count': len(prisoner_credits)},
        ]
        actual_related_credits, likely_truncated = AcceptOrRejectCheckView().get_related_credits(
            api_session=mock_api_session,
            detail_object={
                'credit': {
                    'id': self.credit_id,
                    'prisoner_profile': self.prisoner_id,
                    'sender_profile': self.sender_id
                }
            }
        )
        self.assertListEqual(expected_related_credits, actual_related_credits)
        self.assertFalse(likely_truncated)

    def test_credit_history_truncation(self):
        mock_api_session = mock.MagicMock()
        mock_api_session.get().json.side_effect = [
            {'results': [], 'count': SECURITY_FORMS_DEFAULT_PAGE_SIZE * 5},
            {'results': [], 'count': SECURITY_FORMS_DEFAULT_PAGE_SIZE * 5},
        ]
        actual_related_credits, likely_truncated = AcceptOrRejectCheckView().get_related_credits(
            api_session=mock_api_session,
            detail_object={
                'credit': {
                    'id': self.credit_id,
                    'prisoner_profile': self.prisoner_id,
                    'sender_profile': self.sender_id
                }
            }
        )
        self.assertTrue(likely_truncated)


class CheckAssignViewTestCase(BaseCheckViewTestCase):
    """
    Tests related to CheckAssignView.
    """
    sender_id = 2
    prisoner_id = 3
    credit_id = 5

    SENDER_CHECK = copy.deepcopy(BaseCheckViewTestCase.SAMPLE_CHECK)
    SENDER_CHECK['credit']['sender_profile'] = sender_id
    SENDER_CHECK['credit']['prisoner_profile'] = prisoner_id
    SENDER_CHECK['credit']['id'] = credit_id

    def test_assign_view_get_request_redirects_to_resolve_check_page(self):
        """
        A GET request should redirect to the resolve page
        For instance if a session expires and the user hits 'Add to my list'
        """
        check_id = 1
        response_len = 0
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=dict(self.SENDER_CHECK, assigned_to_name='Columbo', assigned_to=777)
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            url = reverse('security:assign_check', kwargs={'check_id': check_id})
            response = self.client.get(url, follow=True)

            self.assertRedirects(response, reverse('security:resolve_check', kwargs={'check_id': check_id}))

    def test_assign_view_get_request_redirects_to_list_check_page_with_kwarg(self):
        """
        A GET request should redirect to the checks list page
        """
        check_id = 1
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url('/security/checks/'),
                json={
                    'count': 1,
                    'data': [self.SAMPLE_CHECK]
                }
            )

            url = reverse('security:assign_check_then_list', kwargs={'check_id': check_id, 'page': 1})

            response = self.client.get(url, follow=True)

            self.assertRedirects(
                response, reverse('security:check_list') + f'?page=1#check-row-{check_id}'
            )

    def test_assign_view_get_request_redirects_to_list_check_page_with_kwarg_and_current_page(self):
        """
        A GET request should redirect to the checks list page
        """
        check_id = 1

        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url('/security/checks/'),
                json={
                    'count': 21,
                    'data': [self.SAMPLE_CHECK] * 21
                }
            )

            url = reverse('security:assign_check_then_list', kwargs={'check_id': check_id, 'page': 2})

            response = self.client.get(url, follow=True)

            self.assertRedirects(
                response, reverse('security:check_list') + f'?page=2#check-row-{check_id}'
            )
            self.assertContains(response, 'Page 2 of 2')

    def test_can_assign_check_to_own_list(self):
        """
        Test that a user can add a check to their own list of checks
        """
        check_id = 1
        response_len = 0
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.PATCH,
                api_url(f'/security/checks/{check_id}/'),
                json={
                    'count': 1,
                    'results': dict(self.SENDER_CHECK, assigned_to_name='Sherlock Holmes', assigned_to=5),
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=dict(self.SENDER_CHECK, assigned_to_name='Sherlock Holmes', assigned_to=5)
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            url = reverse('security:assign_check', kwargs={'check_id': check_id})

            response = self.client.post(
                url,
                data={
                    'assignment': 'assign',
                },
                follow=True,
            )

            self.assertRedirects(response, reverse('security:resolve_check', kwargs={'check_id': check_id}))
            self.assertContains(response, 'Remove from my list')

    def test_can_remove_check_from_their_list(self):
        """
        Test that a user can add a check to their own list of checks
        """
        check_id = 1
        response_len = 0
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.PATCH,
                api_url(f'/security/checks/{check_id}/'),
                json={
                    'count': 1,
                    'results': dict(self.SENDER_CHECK, assigned_to_name=None, assigned_to=None),
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=dict(self.SENDER_CHECK, assigned_to_name=None, assigned_to=None)
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            url = reverse('security:assign_check', kwargs={'check_id': check_id})

            response = self.client.post(
                url,
                data={
                    'assignment': 'unassign',
                },
                follow=True,
            )

            calls = list(rsps.calls)
            self.assertTrue(json.loads(calls[3].request.body) == {'assigned_to': None})
            self.assertRedirects(response, reverse('security:resolve_check', kwargs={'check_id': check_id}))
            self.assertContains(response, 'Add to my list')

    def test_resolve_page_displays_other_username_if_assigned_else(self):
        """
        Test that a user can see that a different user has already assigned the check to their list
        """
        check_id = 1
        response_len = 0
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=dict(self.SENDER_CHECK, assigned_to_name='Joe Bloggs', assigned_to=200)
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            url = reverse('security:resolve_check', kwargs={'check_id': check_id})

            response = self.client.get(
                url,
                follow=True,
            )

            self.assertNotContains(response, 'name="assignment"')
            self.assertContains(response, 'Added to Joe Bloggs’ list')

    @mock.patch('security.forms.check.get_need_attention_date')
    def test_resolve_page_displays_error_if_assignment_collision_from_list(self, mock_get_need_attention_date):
        """
        Test that a user sees an error if trying to assign check to self that's already assigned to someone else from
        check list view
        """
        mock_get_need_attention_date.return_value = timezone.make_aware(datetime.datetime(2019, 7, 2, 9))

        check_id = 1
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.PATCH,
                api_url(f'/security/checks/{check_id}/'),
                status=400,
                json=[
                    'That check is already assigned to Someone Else'
                ]
            )
            # for checks list after redirect:
            self.mock_first_page_of_checks(rsps, 1)
            self.mock_my_list_count(rsps, 1)
            self.mock_need_attention_count(rsps, mock_get_need_attention_date.return_value)

            url = reverse('security:assign_check_then_list', kwargs={'check_id': check_id, 'page': 1})

            with silence_logger():
                response = self.client.post(
                    url,
                    follow=True,
                    data={'assignment': 'assign'}
                )

            self.assertNotContains(response, 'name="assignment"')
            self.assertContains(response, 'That check is already assigned to Someone Else')
            self.assertRedirects(response, reverse('security:check_list'))

    def test_resolve_page_displays_error_if_assignment_collision_from_accept_reject(self):
        """
        Test that a user sees an error if trying to assign check to self that's already assigned to someone else from
        accept reject check view
        """
        check_id = 1
        response_len = 0
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/security/checks/{check_id}/'),
                json=self.SENDER_CHECK
            )
            rsps.add(
                rsps.PATCH,
                api_url(f'/security/checks/{check_id}/'),
                status=400,
                json=[
                    'That check is already assigned to Someone Else'
                ]
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                        sender_profile_id=self.sender_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', self.credit_id),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                urljoin(
                    settings.API_URL,
                    '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                        prisoner_profile_id=self.prisoner_id,
                        querystring=urlencode([
                            ('limit', SECURITY_FORMS_DEFAULT_PAGE_SIZE),
                            ('offset', 0),
                            ('exclude_credit__in', ','.join(map(str, ([self.credit_id] + list(range(response_len)))))),
                            ('security_check__isnull', False),
                            ('only_completed', False),
                            ('security_check__actioned_by__isnull', False),
                            ('include_checks', True),
                        ])
                    ),
                    trailing_slash=False
                ),
                match_querystring=True,
                json={
                    'count': 0,
                }
            )
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode((
                        ('prisoner_profile_id', self.SENDER_CHECK['credit']['prisoner_profile']),
                        (
                            'debit_card_sender_details_id',
                            self.SENDER_CHECK['credit']['billing_address']['debit_card_sender_details']
                        )
                    ))
                ),
                match_querystring=True,
                json={'count': 0, 'prev': None, 'next': None, 'results': []}
            )

            url = reverse('security:assign_check', kwargs={'check_id': check_id})

            with silence_logger():
                response = self.client.post(
                    url,
                    follow=True,
                    data={'assignment': 'assign'}
                )

            self.assertNotContains(response, 'name="assignment"')
            self.assertContains(response, 'That check is already assigned to Someone Else')
            self.assertRedirects(response, reverse('security:resolve_check', kwargs={'check_id': check_id}))


class AutoAcceptListViewTestCase(BaseCheckViewTestCase):
    """
    Tests related to AutoAcceptListView.
    """

    @staticmethod
    def _only_active_states(states):
        return list(filter(lambda x: x['active'], states))

    def test_cannot_access_view(self):
        """
        Test that if the logged in user doesn't have the right permissions, he/she
        gets redirected to the dashboard.
        """
        user_data = self.get_user_data(permissions=required_permissions)
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps, user_data=user_data)
            response = self.client.get(reverse('security:auto_accept_rule_list'), follow=True)
            self.assertRedirects(response, reverse('security:dashboard'))

    def test_view(self):
        """
        Test that the view displays all auto-accepts returned by the API.
        """
        api_auto_accept_response_len = 50
        page_size = SECURITY_FORMS_DEFAULT_PAGE_SIZE
        api_auto_accept_response = self._generate_auto_accept_response(api_auto_accept_response_len, page_size)

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_my_list_count(rsps)
            rsps.add(
                rsps.GET,
                api_url('/security/checks/auto-accept/'),
                json=api_auto_accept_response
            )

            response = self.client.get(reverse('security:auto_accept_rule_list'), follow=True)

            self.assertEqual(response.status_code, 200)
            content = response.content.decode()
            for resp in api_auto_accept_response['results']:
                self.assertIn(f'************{resp["debit_card_sender_details"]["card_number_last_digits"]}', content)
                self.assertIn(resp['debit_card_sender_details']['cardholder_names'][0], content)
                self.assertIn(resp['prisoner_profile']['prisoner_number'], content)
                self.assertIn(resp['prisoner_profile']['prisoner_name'], content)
                self.assertIn(
                    '{first_name} {last_name}'.format(
                        last_name=self._only_active_states(resp['states'])[-1]['added_by']['last_name'],
                        first_name=self._only_active_states(resp['states'])[-1]['added_by']['first_name']
                    ),
                    content
                )
                self.assertIn(
                    parser.isoparse(
                        self._only_active_states(resp['states'])[-1]['created']
                    ).strftime('%d/%m/%Y %H:%M'),
                    content
                )
                self.assertIn(
                    f'{api_auto_accept_response_len} auto accepts',
                    content
                )

    def test_auto_accept_list_ordering(self):
        """
        Test that the auto_accept list is correctly ordered by parameter passed in
        """
        api_auto_accept_response_len = 50
        page_size = SECURITY_FORMS_DEFAULT_PAGE_SIZE
        api_auto_accept_response = self._generate_auto_accept_response(api_auto_accept_response_len, page_size)
        api_auto_accept_response['results'] = sorted(
            api_auto_accept_response['results'],
            key=lambda aa: self._only_active_states(aa['states'])[-1]['created']
        )

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_my_list_count(rsps)
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode([
                        ('ordering', '-states__added_by__first_name'),
                        ('is_active', True),
                        ('offset', 0),
                        ('limit', page_size),
                    ])
                ),
                match_querystring=True,
                json=api_auto_accept_response
            )

            response = self.client.get(
                '{}?{}'.format(
                    reverse('security:auto_accept_rule_list'),
                    urlencode((
                        ('ordering', '-states__added_by__first_name'),
                        ('is_active', True),
                        ('offset', 0),
                        ('limit', page_size),
                    ))
                ),
                follow=True
            )
            self.assertEqual(response.status_code, 200)
        # Implicit assertion here that RequestsMock was called with parameters specified above
        # once context manager __exit__ called


class AutoAcceptDetailViewTestCase(BaseCheckViewTestCase):

    @parameterized.expand([(True,), (False,)])
    def test_auto_accept_detail_render_auto_accept_rule(self, auto_accept_active):
        """
        Test that the auto_accept detail correctly renders auto_accept_rule
        """
        # Setup
        auto_accept = self._generate_auto_accept_response(
            1, 1, active=auto_accept_active, number_of_cardholder_names=3
        )['results'][0]

        with responses.RequestsMock() as rsps:
            self.login(rsps)
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/{}/'.format(
                    settings.API_URL,
                    auto_accept['id']
                ),
                json=auto_accept
            )

            # Execute
            response = self.client.get(
                reverse(
                    'security:auto_accept_rule_detail',
                    kwargs={'auto_accept_rule_id': auto_accept['id']}
                ),
                follow=True
            )

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Review auto accept of credits from {} and 2 more names to {}'.format(
                auto_accept['debit_card_sender_details']['cardholder_names'][0],
                auto_accept['prisoner_profile']['prisoner_name']
            )
        )

        self.assertContains(
            response,
            parser.isoparse(
                auto_accept['states'][0]['created']
            ).strftime('%d/%m/%Y %H:%M')
        )
        self.assertContains(
            response,
            '{first_name} {last_name}'.format(
                last_name=auto_accept['states'][0]['added_by']['last_name'],
                first_name=auto_accept['states'][0]['added_by']['first_name'],
            )
        )
        self.assertContains(
            response,
            auto_accept['states'][0]['reason']
        )
        self.assertContains(response, 'Start')

        if auto_accept_active:
            self.assertContains(response, 'To stop auto accept:')
            self.assertContains(response, 'Give reason why auto accept is to stop')
            self.assertContains(response, 'Stop auto accept')
        else:
            self.assertContains(
                response,
                parser.isoparse(
                    auto_accept['states'][1]['created']
                ).strftime('%d/%m/%Y %H:%M')
            )
            self.assertContains(
                response,
                '{first_name} {last_name}'.format(
                    last_name=auto_accept['states'][1]['added_by']['last_name'],
                    first_name=auto_accept['states'][1]['added_by']['first_name'],
                )
            )
            self.assertContains(
                response,
                auto_accept['states'][1]['reason']
            )
            self.assertContains(response, 'Stop')
            self.assertNotContains(response, 'To stop auto accept:')
            self.assertNotContains(response, 'Give details why auto accept is to stop')
            self.assertNotContains(response, 'Stop auto accept')

    def test_auto_accept_detail_deactivate_auto_accept_rule(self):
        # Setup
        api_auto_accept_response_len = 50
        page_size = SECURITY_FORMS_DEFAULT_PAGE_SIZE
        auto_accept_list = self._generate_auto_accept_response(api_auto_accept_response_len, page_size)
        auto_accept_detail = self._generate_auto_accept_response(1, 1, active=True)['results'][0]
        deactivation_reason = 'Oops, butterfingers!'
        with responses.RequestsMock() as rsps:
            self.login(rsps)
            self.mock_my_list_count(rsps)
            rsps.add(
                rsps.GET,
                '{}/security/checks/auto-accept/?{}'.format(
                    settings.API_URL,
                    urlencode([
                        ('ordering', '-states__created'),
                        ('is_active', True),
                        ('offset', 0),
                        ('limit', page_size),
                    ])
                ),
                match_querystring=True,
                json=auto_accept_list
            )

            rsps.add(
                rsps.PATCH,
                '{}/security/checks/auto-accept/{}/'.format(
                    settings.API_URL,
                    auto_accept_detail['id']
                ),
                json=auto_accept_detail
            )

            # Execute
            response = self.client.post(
                reverse(
                    'security:auto_accept_rule_detail',
                    kwargs={'auto_accept_rule_id': auto_accept_detail['id']}
                ),
                data={
                    'deactivation_reason': deactivation_reason,
                },
                follow=True
            )

            self.assertRedirects(response, reverse('security:auto_accept_rule_list'))
            self.assertContains(response, 'The auto accept was stopped')
            patch_calls = list(filter(lambda call: call.request.method == rsps.PATCH, rsps.calls))
            self.assertEqual(len(patch_calls), 1)
            patch_request_body = json.loads(patch_calls[0].request.body)
            self.assertDictEqual(
                patch_request_body,
                {
                    'states': [{
                        'active': False,
                        'reason': deactivation_reason
                    }]
                }
            )
