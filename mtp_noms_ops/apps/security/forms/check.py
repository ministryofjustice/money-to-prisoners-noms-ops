import logging
from functools import lru_cache

from django.forms import forms
from django.utils.translation import gettext_lazy
from requests.exceptions import RequestException

from security.forms.object_base import SecurityDetailForm, SecurityForm
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


class AcceptCheckForm(SecurityDetailForm):
    """
    Accepts a check.
    """

    def get_object_endpoint_path(self):
        return f'/security/checks/{self.object_id}/'

    def get_accept_object_endpoint_path(self):
        return f'/security/checks/{self.object_id}/accept/'

    @lru_cache()
    def get_object(self):
        """
        Gets the object data and converts datetimes found in it.
        """
        return convert_date_fields(super().get_object(), include_nested=True)

    def check_and_update_saved_searches(self, page_title):
        """
        Overrides the logic in the superclass.
        """

    def get_object_list(self):
        """
        Overrides the logic in the superclass.
        """
        return []

    def clean(self):
        """
        Makes sure that the check is in pending.
        """
        if self.get_object()['status'] != 'pending':
            raise forms.ValidationError(
                gettext_lazy("You cannot accept this payment as it's not in pending"),
            )
        return super().clean()

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
