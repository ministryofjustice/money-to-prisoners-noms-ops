import logging
from functools import lru_cache

from django import forms
from django.contrib import messages
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth.api_client import get_api_session
from requests.exceptions import RequestException

from security.forms.object_base import SecurityForm
from security.utils import convert_date_fields, get_need_attention_date

logger = logging.getLogger('mtp')


class CheckListForm(SecurityForm):
    """
    List of security checks.
    """

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        self.need_attention_date = get_need_attention_date()
        self.need_attention_count = 0
        self.my_list_count = 0

    def get_api_request_params(self):
        """
        Gets pending checks only, for now.
        """
        return dict(
            super().get_api_request_params(),
            **{
                'status': 'pending',
                'credit_resolution': 'initial'
            }
        )

    def get_object_list_endpoint_path(self):
        return '/security/checks/'

    def get_object_list(self):
        """
        Gets objects, converts datetimes found in them and looks up count of urgent checks.
        """
        # TODO this second API call feels unnecessary, look at refactoring it out and implementing date filtering logic
        # in python space
        self.need_attention_count = self.session.get(self.get_object_list_endpoint_path(), params=dict(
            self.get_api_request_params(),
            **{
                'started_at__lt': self.need_attention_date.strftime('%Y-%m-%d %H:%M:%S'),
                'offset': 0,
                'limit': 1,
            }
        )).json()['count']
        self.my_list_count = self.session.get(self.get_object_list_endpoint_path(), params=dict(
            self.get_api_request_params(),
            **{
                'assigned_to': self.request.user.pk,
                'offset': 0,
                'limit': 1,
            }
        )).json()['count']

        object_list = convert_date_fields(super().get_object_list(), include_nested=True)
        for check in object_list:
            check['needs_attention'] = check['credit']['started_at'] < self.need_attention_date

        return object_list


class UserCheckListForm(CheckListForm):

    def get_api_request_params(self):
        return dict(
            super().get_api_request_params(),
            assigned_to=self.request.user.pk
        )


class CreditsHistoryListForm(SecurityForm):
    """
    List of security checks.
    """
    CHECKS_STARTED = '2020-01-02T12:00:00'

    ordering = forms.ChoiceField(
        label=_('Order by'),
        required=False,
        initial='-created',
        choices=[
            ('created', _('Date started (oldest to newest)')),
            ('-created', _('Date started (newest to oldest)')),
        ],
    )

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        self.my_list_count = 0

    def get_api_request_params(self):
        """
        Gets all checks where actioned_by is not None.
        """
        params = super().get_api_request_params()
        params['actioned_by'] = True
        params['started_at__gte'] = self.CHECKS_STARTED
        return params

    def get_object_list_endpoint_path(self):
        return '/security/checks/'

    def get_object_list(self):
        """
        Gets objects, converts datetimes found in them.
        """
        object_list = convert_date_fields(super().get_object_list(), include_nested=True)
        self.my_list_count = self.session.get(self.get_object_list_endpoint_path(), params=dict(
            self.get_api_request_params(),
            **{
                'assigned_to': self.request.user.pk,
                'offset': 0,
                'limit': 1,
            }
        )).json()['count']
        return object_list


class AcceptOrRejectCheckForm(GARequestErrorReportingMixin, forms.Form):
    """
    CheckForm for accepting or rejecting a check.
    """
    decision_reason = forms.CharField(
        label=_('Give details (details are optional when accepting)'),
        required=False,
    )
    fiu_action = forms.CharField(max_length=10)

    def __init__(self, object_id, request, **kwargs):
        super().__init__(**kwargs)
        self.object_id = object_id
        self.need_attention_date = get_need_attention_date()
        self.request = request

    @lru_cache()
    def get_object(self):
        """
        Gets the check object
        :return: dict or None if not found
        """
        try:
            obj = self.session.get(self.get_object_endpoint_path()).json()
            convert_dates_obj = convert_date_fields(obj, include_nested=True)
            convert_dates_obj['needs_attention'] = convert_dates_obj['credit']['started_at'] < self.need_attention_date
            return obj
        except RequestException:
            return None

    def get_object_endpoint_path(self):
        return f'/security/checks/{self.object_id}/'

    @cached_property
    def session(self):
        return get_api_session(self.request)

    def clean(self):
        """
        Makes sure that the check is in pending.
        """
        status = self.cleaned_data['fiu_action']
        if 'decision_reason' in self.cleaned_data:
            reason = self.cleaned_data['decision_reason']
        else:
            reason = ''

        if not reason and status == 'reject':
            msg = forms.ValidationError('This field is required')
            self.add_error('decision_reason', msg)

        if not self.errors:  # if already in error => skip
            if self.get_object()['status'] != 'pending':
                raise forms.ValidationError(
                    _('You cannot action this credit as it’s not in pending'),
                )
        return super().clean()

    def get_resolve_endpoint_path(self, fiu_action='accept'):
        return f'/security/checks/{self.object_id}/{fiu_action}/'

    def accept_or_reject(self):
        """
        Accepts or rejects the check via the API.
        :return: True if the API call was successful.
            If not, it returns False and populating the self.errors dict.
        """
        endpoint = self.get_resolve_endpoint_path(fiu_action=self.cleaned_data['fiu_action'])

        try:
            self.session.post(
                endpoint,
                json={
                    'decision_reason': self.cleaned_data['decision_reason'],
                }
            )
            return True
        except RequestException:
            logger.exception(f'Check {self.object_id} could not be actioned')
            self.add_error(None, _('There was an error with your request.'))
            return False


class AssignCheckToUserForm(GARequestErrorReportingMixin, forms.Form):
    assignment = forms.ChoiceField(
        choices=[
            ('assign', _('Assign')),
            ('unassign', _('Unassign')),
        ],
        required=True
    )

    def __init__(self, object_id, request, **kwargs):
        super().__init__(**kwargs)
        self.object_id = object_id
        self.request = request

    @cached_property
    def session(self):
        return get_api_session(self.request)

    def get_endpoint_path(self):
        return f'/security/checks/{self.object_id}/'

    def assign_or_unassign(self):
        endpoint = self.get_endpoint_path()

        if self.cleaned_data.get('assignment') == 'assign':
            user_id = self.request.user.pk
        elif self.cleaned_data.get('assignment') == 'unassign':
            user_id = None

        try:
            self.session.patch(
                endpoint,
                json={
                    'assigned_to': user_id
                }
            )
            return True
        except RequestException:
            logger.exception(f'Check {self.object_id} could not be assigned')
            messages.add_message(
                self.request,
                messages.ERROR,
                _('There was an error with your request.')
            )
            return False
