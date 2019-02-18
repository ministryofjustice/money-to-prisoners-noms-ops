import logging
from urllib.parse import urlencode

from django import forms
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from mtp_common.api import retrieve_all_pages_for_path
from mtp_common.user_admin.forms import ApiForm
from oauthlib.oauth2 import OAuth2Error
from requests import RequestException

from security.utils import refresh_user_data

logger = logging.getLogger('mtp')


def prison_choices(api_session):
    choices = cache.get('prison-list')
    if not choices:
        try:
            choices = retrieve_all_pages_for_path(api_session, '/prisons/', exclude_empty_prisons=True)
            choices = [[prison['nomis_id'], prison['name']] for prison in choices]
            cache.set('prison-list', choices, timeout=60 * 60 * 6)
        except (RequestException, OAuth2Error, ValueError):
            logger.exception('Could not look up prison list')
    return choices


class ChoosePrisonForm(ApiForm):
    new_prison = forms.ChoiceField(
        label=_('Add a prison'),
        help_text=_('We only have data for public prisons'),
        choices=[],
        required=False,
    )
    prisons = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )
    error_messages = {
        'no_prison_selected': _('Choose a prison'),
        'already_chosen': _('You have already added that prison'),
        'no_prisons_added': _('You must add at least one prison'),
        'generic': _('This service is currently unavailable'),
    }
    actions = ['choose', 'confirm']
    all_prisons_code = 'ALL'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_prisons = self.request.GET.getlist('prisons') or []
        prison_list = prison_choices(self.api_session)

        self.fields['new_prison'].choices = [
            ['', _('Select a prison')],
        ] + prison_list

        self.fields['prisons'].choices = [
            [self.all_prisons_code, _('All prisons')]
        ] + prison_list

        selected_prisons = self.request.GET.getlist('prisons')
        if selected_prisons:
            self.fields['prisons'].initial = selected_prisons
        else:
            if self.request.user_prisons:
                self.fields['prisons'].initial = [
                    prison['nomis_id'] for prison in self.request.user_prisons
                ]
            else:
                self.fields['prisons'].initial = [self.all_prisons_code]

        self.selected_prisons = []
        for prison, label in self.fields['prisons'].choices:
            if prison in self.fields['prisons'].initial:
                query_dict = self.request.GET.copy()
                other_prisons = set(query_dict.getlist('prisons'))
                if prison in other_prisons:
                    other_prisons.remove(prison)
                query_dict['prisons'] = list(other_prisons) or ''
                removal_link = urlencode(query_dict, doseq=True)
                self.selected_prisons.append(
                    (label, removal_link)
                )

        if self.is_bound:
            self.action = None
            for action in self.actions:
                key = 'submit_%s' % action
                if key in self.request.POST:
                    self.action = action

    def clean_new_prison(self):
        if self.action == 'choose':
            if not self.cleaned_data['new_prison']:
                raise forms.ValidationError(self.error_messages['no_prison_selected'])
            query_dict = self.request.GET.copy()
            current_prisons = query_dict.getlist('prisons')
            if self.cleaned_data['new_prison'] in current_prisons:
                raise forms.ValidationError(self.error_messages['already_chosen'])
        return self.cleaned_data['new_prison']

    def clean_prisons(self):
        if self.action == 'confirm':
            if not self.cleaned_data['prisons']:
                raise forms.ValidationError(self.error_messages['no_prisons_added'])
        return self.cleaned_data['prisons']

    def get_query_string(self):
        query_dict = self.request.GET.copy()
        current_prisons = self.fields['prisons'].initial
        if current_prisons == [self.all_prisons_code]:
            current_prisons = []
        current_prisons.append(self.cleaned_data['new_prison'])
        query_dict['prisons'] = current_prisons or ''
        return urlencode(query_dict, doseq=True)

    def save(self):
        try:
            prisons = self.cleaned_data['prisons']
            if self.all_prisons_code in prisons:
                prisons = []
            self.api_session.patch(
                '/users/%s/' % (self.request.user.username),
                json={
                    'prisons': [
                        {'nomis_id': prison} for prison in prisons
                    ]
                }
            )
            refresh_user_data(self.request, self.api_session)
        except RequestException as e:
            self.api_validation_error(e)
