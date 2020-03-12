import datetime
import logging
from functools import lru_cache

from django import forms
from django.conf import settings
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth.api_client import get_api_session
from mtp_common.auth.exceptions import HttpNotFoundError
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

    def get_api_request_params(self):
        """
        Gets pending checks only, for now.
        """
        params = super().get_api_request_params()
        params['status'] = 'pending'
        # TODO: always add credit_resolution filter following delayed capture release
        if settings.SHOW_ONLY_CHECKS_WITH_INITIAL_CREDIT:
            params['credit_resolution'] = 'initial'
        return params

    def get_object_list_endpoint_path(self):
        return '/security/checks/'

    def get_object_list(self):
        """
        Gets objects, converts datetimes found in them and looks up count of urgent checks.
        """
        self.need_attention_count = self.session.get(self.get_object_list_endpoint_path(), params={
            'status': 'pending',
            'started_at__lt': self.need_attention_date.strftime('%Y-%m-%d %H:%M:%S'),
            'offset': 0,
            'limit': 1,
        }).json()['count']

        object_list = convert_date_fields(super().get_object_list(), include_nested=True)
        for check in object_list:
            check['needs_attention'] = check['credit']['started_at'] < self.need_attention_date

        return object_list


class AcceptOrRejectCheckForm(GARequestErrorReportingMixin, forms.Form):
    """
    Base CheckForm for accepting or rejecting a check.
    """

    rejection_reason = forms.CharField(
        label=gettext_lazy('Give details (details are optional when accepting)'),
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
        Gets the security detail object, a sender or prisoner profile
        :return: dict or None if not found
        """
        try:
            obj = self.session.get(self.get_object_endpoint_path()).json()
            convert_dates_obj = convert_date_fields(obj, include_nested=True)
            convert_dates_obj['needs_attention'] = convert_dates_obj['credit']['started_at'] < self.need_attention_date
            return obj
        except HttpNotFoundError:
            self.add_error(None, gettext_lazy('Not found'))
            return None
        except RequestException:
            self.add_error(None, gettext_lazy('This service is currently unavailable'))
            return {}

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
        if 'rejection_reason' in self.cleaned_data:
            reason = self.cleaned_data['rejection_reason']
        else:
            reason = ''

        if reason == '' and status == 'reject':
            msg = forms.ValidationError('This field is required')
            self.add_error('rejection_reason', msg)

        if not self.errors:  # if already in error => skip
            if self.get_object()['status'] != 'pending':
                raise forms.ValidationError(
                    gettext_lazy("You cannot action this credit as it's not in pending"),
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
                    'rejection_reason': self.cleaned_data['rejection_reason'],
                }
            )
            return True
        except RequestException:
            logger.exception(f'Check {self.object_id} could not be actioned')
            self.add_error(None, gettext_lazy('There was an error with your request.'))
            return False
