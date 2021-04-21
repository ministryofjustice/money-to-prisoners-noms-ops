from collections import OrderedDict
import logging
from urllib.parse import urlencode

from django import forms
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from mtp_common.api import retrieve_all_pages_for_path
from mtp_common.user_admin.forms import ApiForm
from requests import RequestException

from security.utils import refresh_user_data

logger = logging.getLogger('mtp')

ALL_PRISONS_CODE = 'ALL'


def prison_choices(api_session):
    choices = cache.get('prison-list')
    if not choices:
        choices = retrieve_all_pages_for_path(api_session, '/prisons/', exclude_empty_prisons=True)
        choices = [[prison['nomis_id'], prison['name']] for prison in choices]
        cache.set('prison-list', choices, timeout=60 * 60 * 6)
    return choices


class ConfirmPrisonForm(ApiForm):
    prisons = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )
    all_prisons_code = ALL_PRISONS_CODE
    error_messages = {
        'generic': _('This service is currently unavailable'),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        prison_list = prison_choices(self.api_session)

        self.fields['prisons'].choices = [
            [self.all_prisons_code, _('All prisons')]
        ] + prison_list

        selected_prisons = self.request.GET.getlist('prisons') or []
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
                self.selected_prisons.append(
                    (prison, label)
                )

    def save(self):
        try:
            prisons = self.cleaned_data['prisons']
            if self.all_prisons_code in prisons:
                prisons = []

            logger.info('%(user)s confirmed prisons %(current)s > %(new)s', {
                'user': self.request.user.username,
                'current': [
                    prison['nomis_id'] for prison in self.request.user_prisons
                ],
                'new': prisons
            })
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


class ChangePrisonForm(ApiForm):
    all_prisons = forms.BooleanField(required=False)
    template_prison_selection = forms.ChoiceField(
        label=_('Prison'),
        choices=[],
        required=False,
        initial=''
    )
    error_messages = {
        'already_chosen': _('You have already added that prison'),
        'no_prisons_added': _('You must add at least one prison'),
        'generic': _('This service is currently unavailable'),
    }
    all_prisons_code = ALL_PRISONS_CODE
    actions = ['save', 'add', 'remove', 'all', 'notall']

    def __init__(self, **kwargs):
        self.action = None
        removed_item = None
        for action in self.actions:
            for key in kwargs['request'].POST:
                if key.startswith('submit_%s' % action):
                    self.action = action
                    if action == 'remove':
                        removed_item = key[14:]
                        kwargs['data'] = kwargs['data'].copy()
                        del kwargs['data'][removed_item]

        if self.action == 'all':
            kwargs['data'] = kwargs['data'].copy()
            kwargs['data']['all_prisons'] = True
        elif self.action == 'notall':
            kwargs['data'] = kwargs['data'].copy()
            kwargs['data']['all_prisons'] = False

        super().__init__(**kwargs)
        self.build_prison_fields(removed_item)

    def build_prison_fields(self, removed_item):
        prison_list = prison_choices(self.api_session)
        self.new_prisons = set()

        self.fields['template_prison_selection'].choices = [
            ['', _('Select a prison')]
        ] + prison_list

        if self.is_bound:
            self.prison_keys = sorted([
                key for key in self.request.POST
                if key.startswith('prison_') and
                key != removed_item
            ])
            for key in self.prison_keys:
                self.create_prison_field(key, prison_list)
        else:
            if 'prisons' in self.request.GET:
                initial_prisons = self.request.GET.getlist('prisons') or []
                if self.all_prisons_code in initial_prisons:
                    self.fields['all_prisons'].initial = True
                else:
                    for i, prison in enumerate(initial_prisons):
                        field_name = 'prison_%s' % i
                        self.create_prison_field(
                            field_name, prison_list, initial=prison
                        )
            else:
                if self.request.user_prisons:
                    for i, prison in enumerate(self.request.user_prisons):
                        field_name = 'prison_%s' % i
                        self.create_prison_field(
                            field_name, prison_list, initial=prison['nomis_id']
                        )
                else:
                    self.fields['all_prisons'].initial = True

        if self.action == 'add' or not self.prison_fields:
            next_prison_id = 0
            for __ in self.prison_fields:
                if next_prison_id < int(key[7:]):
                    next_prison_id = int(key[7:])
            field_name = 'prison_%s' % (next_prison_id + 1)
            self.create_prison_field(field_name, prison_list)

    def create_prison_field(self, fieldname, prison_list, initial=None):
        self.fields[fieldname] = forms.ChoiceField(
            label=_('Prison'),
            choices=[['', _('Select a prison')]] + prison_list,
            required=False,
            initial=initial
        )
        setattr(
            self,
            'clean_%s' % fieldname,
            self.get_clean_prison_method(fieldname)
        )

    @property
    def prison_fields(self):
        return OrderedDict(sorted([
            (k, self.fields[k]) for k in self.fields if k.startswith('prison_')
        ], key=lambda f: f[0]))

    def is_valid(self):
        if self.action != 'save':
            return False
        return super().is_valid()

    def get_clean_prison_method(self, field_name):
        def clean_prison():
            if (
                self.cleaned_data[field_name] and
                self.cleaned_data[field_name] in self.new_prisons
            ):
                raise forms.ValidationError(self.error_messages['already_chosen'])
            self.new_prisons.add(self.cleaned_data[field_name])
            return self.cleaned_data[field_name]
        return clean_prison

    def clean_template_prison_selection(self):
        return None

    def clean(self):
        if self.action == 'save' and not self.cleaned_data['all_prisons']:
            some_values = False
            for field_name in self.prison_fields:
                if self.cleaned_data.get(field_name):
                    some_values = True

            if not some_values:
                if self.prison_fields:
                    self.add_error(
                        list(self.prison_fields.keys())[0],
                        forms.ValidationError(self.error_messages['no_prisons_added'])
                    )
                else:
                    raise forms.ValidationError(self.error_messages['no_prisons_added'])
        return self.cleaned_data

    def save(self):
        try:
            prisons = []
            if not self.cleaned_data['all_prisons']:
                for field_name in self.prison_fields:
                    if self.cleaned_data[field_name]:
                        prisons.append(self.cleaned_data[field_name])

            logger.info('%(user)s confirmed prisons %(current)s > %(new)s', {
                'user': self.request.user.username,
                'current': [
                    prison['nomis_id'] for prison in self.request.user_prisons
                ],
                'new': prisons,
            })
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

    def get_confirmation_query_string(self):
        prisons = []
        if self.cleaned_data['all_prisons']:
            prisons.append(self.all_prisons_code)
        for field_name in self.prison_fields:
            if self.cleaned_data[field_name]:
                prisons.append(self.cleaned_data[field_name])

        query_dict = self.request.GET.copy()
        query_dict['prisons'] = prisons
        return urlencode(query_dict, doseq=True)


class JobInformationForm(ApiForm):
    job_titles = [
        ('Evidence collator', _('Evidence collator')),
        ('Intelligence analyst', _('Intelligence analyst')),
        ('Intelligence officer', _('Intelligence officer')),
        ('Intelligence researcher', _('Intelligence researcher')),
        ('Intelligence support officer', _('Intelligence support officer')),
        ('Safety analyst', _('Safety analyst')),
        ('Security analyst', _('Security analyst')),
        ('Other', _('Other'))
    ]

    prison_estates = [
        ('Local prison', _('Local prison')),
        ('Regional', _('Regional')),
        ('National', _('National')),
    ]
    job_title = forms.ChoiceField(label=_('What is your job title?'),
                                  choices=job_titles)
    prison_estate = forms.ChoiceField(label=_('Which area of the prison estate do you work in?'),
                                      choices=prison_estates)
    tasks = forms.CharField(label=_('What are your main tasks?'),
                            help_text=_('Give a brief description.'))

    other_title = forms.CharField(max_length=100,
                                  label=_('Tell us your job title'),
                                  required=False)

    def clean(self):
        if 'job_title' in self.cleaned_data:
            if self.cleaned_data['job_title'] == 'Other':
                if self.cleaned_data['other_title'] == '':
                    self.add_error('other_title', _('Please enter your job title'))
                else:
                    self.cleaned_data['job_title_or_other'] = self.cleaned_data['other_title']
            else:
                self.cleaned_data['job_title_or_other'] = self.cleaned_data['job_title']

        return self.cleaned_data
