import logging
from functools import lru_cache

from django import forms
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth.api_client import get_api_session
from mtp_common.auth.exceptions import HttpNotFoundError
from requests.exceptions import RequestException

from security.forms.object_base import SecurityForm
from security.utils import convert_date_fields

logger = logging.getLogger('mtp')


class CheckListForm(SecurityForm):
    """
    List of security checks.
    """

    def get_api_request_params(self):
        """
        Gets pending checks only, for now.
        """
        params = super().get_api_request_params()
        params['status'] = 'pending'
        return params

    def get_object_list_endpoint_path(self):
        return '/security/checks/'

    def get_object_list(self):
        """
        Gets objects and converts datetimes found in them.
        """
        return convert_date_fields(super().get_object_list(), include_nested=True)


class ActionCheckForm(GARequestErrorReportingMixin, forms.Form):
    """
    Base CheckForm for accepting or rejecting a check.
    """
    non_pending_error_msg = NotImplementedError

    def __init__(self, object_id, request, **kwargs):
        super().__init__(**kwargs)
        self.object_id = object_id
        self.request = request

    @lru_cache()
    def get_object(self):
        """
        Gets the security detail object, a sender or prisoner profile
        :return: dict or None if not found
        """
        try:
            obj = self.session.get(self.get_object_endpoint_path()).json()
            return convert_date_fields(obj, include_nested=True)
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
        if not self.errors:  # if already in error => skip
            if self.get_object()['status'] != 'pending':
                raise forms.ValidationError(
                    gettext_lazy(self.non_pending_error_msg),
                )
        return super().clean()


class AcceptCheckForm(ActionCheckForm):
    """
    Accepts a check.
    """
    non_pending_error_msg = "You cannot accept this payment as it's not in pending"

    def get_accept_object_endpoint_path(self):
        return f'/security/checks/{self.object_id}/accept/'

    def accept(self):
        """
        Accepts the check via the API.
        :return: True if the API call was successful.
            If not, it returns False and populating the self.errors dict.
        """
        try:
            self.session.post(self.get_accept_object_endpoint_path())
            return True
        except RequestException:
            logger.exception(f'Check {self.object_id} could not be accepted')
            self.add_error(None, gettext_lazy('There was an error with your request.'))
            return False


class RejectCheckForm(ActionCheckForm):
    """
    Rejects a check.
    """
    rejection_reason = forms.CharField(label=gettext_lazy('Give details'), required=True)

    non_pending_error_msg = "You cannot reject this payment as it's not in pending"

    def get_reject_object_endpoint_path(self):
        return f'/security/checks/{self.object_id}/reject/'

    def reject(self):
        """
        Rejects the check via the API.
        :return: True if the API call was successful.
            If not, it returns False and populating the self.errors dict.
        """
        try:
            self.session.post(
                self.get_reject_object_endpoint_path(),
                json={
                    'rejection_reason': self.cleaned_data['rejection_reason'],
                }
            )
            return True
        except RequestException:
            logger.exception(f'Check {self.object_id} could not be rejected')
            self.add_error(None, gettext_lazy('There was an error with your request.'))
            return False
