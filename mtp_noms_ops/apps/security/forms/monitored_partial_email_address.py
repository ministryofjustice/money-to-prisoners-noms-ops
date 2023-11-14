import logging
from urllib.parse import quote

from django import forms
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from mtp_common.auth.api_client import get_api_session
from requests.exceptions import RequestException

from security.forms.check import SecurityFormWithMyListCount

logger = logging.getLogger('mtp')


class MonitoredPartialEmailAddressListForm(SecurityFormWithMyListCount):
    """
    List of monitored partial email addresses
    """

    def get_object_list_endpoint_path(self):
        return '/security/monitored-email-addresses/'


class MonitoredPartialEmailAddressAddForm(forms.Form):
    """
    Add a new monitored partial email address
    """
    keyword = forms.CharField(label=_('Keyword to remove'), required=True, min_length=3, error_messages={
        'min_length': _('Keyword must be a minimum of 3 characters'),
    })

    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request

    @cached_property
    def session(self):
        return get_api_session(self.request)

    @classmethod
    def get_endpoint_path(cls):
        return '/security/monitored-email-addresses/'

    def add_keyword(self):
        try:
            response = self.session.post(
                self.get_endpoint_path(),
                json=self.cleaned_data['keyword'],
            )
            response.raise_for_status()
            return True
        except RequestException:
            logger.exception('Keyword “%(keyword)s” could not be added', {
                'keyword': self.cleaned_data['keyword'],
            })
            return False


class MonitoredPartialEmailAddressDeleteForm(forms.Form):
    """
    Delete a monitored partial email address
    """
    keyword = forms.CharField(label=_('Keyword to remove'), required=True)

    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request

    @cached_property
    def session(self):
        return get_api_session(self.request)

    def get_endpoint_path(self):
        keyword = self.cleaned_data['keyword']
        keyword = quote(keyword, safe='')
        return f'/security/monitored-email-addresses/{keyword}/'

    def delete_keyword(self):
        try:
            response = self.session.delete(self.get_endpoint_path())
            response.raise_for_status()
            return True
        except RequestException:
            logger.exception('Keyword “%(keyword)s” could not be removed', {
                'keyword': self.cleaned_data['keyword'],
            })
            return False
