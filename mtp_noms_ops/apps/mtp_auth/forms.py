import logging

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from mtp_common.user_admin.forms import (
    AcceptRequestForm as AcceptRequestFormBase,
    SignUpForm as BaseSignUpForm,
)
from oauthlib.oauth2 import OAuth2Error
from requests import RequestException
from zendesk_tickets.forms import BaseTicketForm


logger = logging.getLogger('mtp')


class AcceptRequestForm(AcceptRequestFormBase):
    user_admin = forms.BooleanField(
        label=_('This account is for an FIU user (FIU users will be able to manage other user accounts)'),
        required=False,
    )


class SignUpForm(BaseSignUpForm, BaseTicketForm):
    account_request_zendesk_subject = (
        'MTP for digital team - '
        'Prisoner money intelligence - '
        'Request for new staff account'
    )
    zendesk_tags = ('feedback', 'mtp', 'noms-ops', 'account_request', settings.ENVIRONMENT)

    role = forms.CharField(label=_('Role'), initial='security')
    manager_email = forms.EmailField(label=_("Your manager's email"))

    def user_already_requested_account(self):
        try:
            response = self.api_session.get(
                'requests/',
                params={
                    'username': self.cleaned_data['username'],
                    'role__name': self.cleaned_data['role'],
                },
            )
            return response.json().get('count', 0) > 0
        except (RequestException, OAuth2Error, ValueError):
            logger.exception('Could not look up access requests')
            self.add_error(None, _('This service is currently unavailable'))

    def clean(self):
        self.cleaned_data['role'] = 'security'

        if self.is_valid() and self.user_already_requested_account():
            return self.submit_ticket(
                self.request,
                subject=self.account_request_zendesk_subject,
                tags=self.zendesk_tags,
                ticket_template_name='mtp_common/user_admin/new-account-request-ticket.txt',
                requester_email=self.cleaned_data['email'],
            )

        return super().clean()
