import collections
from math import ceil
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth.api_client import get_connection

from mtp_noms_ops.view_utils import make_page_range


def get_prisons_and_regions(client, session):
    prisons_and_regions = session.get('prisons_and_regions')
    if not prisons_and_regions:
        prisons = client.prisons.get().get('results', [])
        prison_choices = [
            (prison['nomis_id'], prison['name'])
            for prison in prisons
        ]
        region_choices = [
            (region, region)
            for region in sorted(set(prison['region'] for prison in prisons))
        ]
        prisons_and_regions = {
            'prisons': prison_choices,
            'regions': region_choices,
        }
        session['prisons_and_regions'] = prisons_and_regions
    return prisons_and_regions


def validate_range_field(field_name, bound_ordering_msg):
    def inner(cls):
        lower = field_name + '_0'
        upper = field_name + '_1'

        def clean(self):
            lower_value = self.cleaned_data.get(lower)
            upper_value = self.cleaned_data.get(upper)
            if lower_value and upper_value and lower_value > upper_value:
                raise ValidationError(bound_ordering_msg or _('Must be greater than the lower bound'),
                                      code='bound_ordering')
            return upper_value

        setattr(cls, 'clean_' + upper, clean)
        return cls

    return inner


@validate_range_field('received_at', _('Must be after the start date'))
class SecurityForm(GARequestErrorReportingMixin, forms.Form):
    """
    Base form for security searches
    Uses 'page' parameter to determine if form is submitted
    """
    page = forms.IntegerField(min_value=1)
    page_size = 20
    ordering = forms.CharField(label=_('Sort by'), required=False)
    received_at_0 = forms.DateField(label=_('Start date'), required=False)
    received_at_1 = forms.DateField(label=_('Finish date'), required=False)

    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request
        self.client = get_connection(request)
        self.page_count = 0

    def get_api_endpoint(self):
        raise NotImplementedError

    def get_query_data(self):
        data = collections.OrderedDict()
        for field in self:
            if field.name == 'page':
                continue
            value = self.cleaned_data.get(field.name)
            if not value:
                continue
            data[field.name] = value
        return data

    def get_object_list(self):
        end_point = self.get_api_endpoint()
        page = self.cleaned_data['page']
        offset = (page - 1) * self.page_size
        data = end_point.get(offset=offset, limit=self.page_size, **self.get_query_data())
        count = data['count']
        self.page_count = int(ceil(count / self.page_size))
        return data.get('results', [])

    @cached_property
    def query_string(self):
        return urlencode(self.get_query_data())

    @property
    def page_range(self):
        return make_page_range(self.cleaned_data['page'], self.page_count)


@validate_range_field('prisoner_count', _('Must be larger than the minimum prisoners'))
@validate_range_field('credit_count', _('Must be larger than the minimum credits'))
@validate_range_field('credit_total', _('Must be larger than the minimum total'))
class SenderGroupedForm(SecurityForm):
    ordering = forms.ChoiceField(label=_('Sort by'), required=False,
                                 initial='-prisoner_count',
                                 choices=[
                                     ('-prisoner_count', _('Number of prisoners')),
                                     ('-credit_count', _('Number of payments')),
                                     ('-credit_total', _('Total sent')),
                                     ('sender_name', _('Sender name')),
                                 ])

    prisoner_count_0 = forms.IntegerField(label=_('Minimum prisoners'), required=False, min_value=1)
    prisoner_count_1 = forms.IntegerField(label=_('Maximum prisoners'), required=False, min_value=1)
    credit_count_0 = forms.IntegerField(label=_('Minimum credits'), required=False, min_value=1)
    credit_count_1 = forms.IntegerField(label=_('Maximum credits'), required=False, min_value=1)
    credit_total_0 = forms.IntegerField(label=_('Minimum total'), required=False)
    credit_total_1 = forms.IntegerField(label=_('Maximum total'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'),
    #                          required=False)

    sender_name = forms.CharField(label=_('Sender name'), required=False)
    sender_sort_code = forms.CharField(label=_('Sender sort code'), required=False)
    sender_account_number = forms.CharField(label=_('Sender account number'), required=False)
    sender_roll_number = forms.CharField(label=_('Sender roll number'), required=False)

    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_gender = forms.ChoiceField(label=_('Prisoner gender'), required=False,
                                      choices=(('m', _('Male')), ('f', _('Female'))))

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prisons_and_regions = get_prisons_and_regions(self.client, request.session)
        self['prison'].field.choices = prisons_and_regions['prisons']
        self['prison_region'].field.choices = prisons_and_regions['regions']

    def clean_sender_sort_code(self):
        sender_sort_code = self.cleaned_data.get('sender_sort_code')
        if sender_sort_code:
            sender_sort_code = sender_sort_code.replace('-', '')
        return sender_sort_code

    def get_api_endpoint(self):
        return self.client.credits.senders


@validate_range_field('sender_count', _('Must be larger than the minimum senders'))
@validate_range_field('credit_count', _('Must be larger than the minimum credits'))
@validate_range_field('credit_total', _('Must be larger than the minimum total'))
class PrisonerGroupedForm(SecurityForm):
    ordering = forms.ChoiceField(label=_('Sort by'), required=False,
                                 initial='-sender_count',
                                 choices=[
                                     ('-sender_count', _('Number of senders')),
                                     ('-credit_count', _('Number of payments')),
                                     ('-credit_total', _('Total sent')),
                                     ('prisoner_name', _('Prisoner name')),
                                     ('prisoner_number', _('Prisoner number')),
                                 ])

    sender_count_0 = forms.IntegerField(label=_('Minimum senders'), required=False, min_value=1)
    sender_count_1 = forms.IntegerField(label=_('Maximum senders'), required=False, min_value=1)
    credit_count_0 = forms.IntegerField(label=_('Minimum credits'), required=False, min_value=1)
    credit_count_1 = forms.IntegerField(label=_('Maximum credits'), required=False, min_value=1)
    credit_total_0 = forms.IntegerField(label=_('Minimum total'), required=False)
    credit_total_1 = forms.IntegerField(label=_('Maximum total'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'),
    #                          required=False)

    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_gender = forms.ChoiceField(label=_('Prisoner gender'), required=False,
                                      choices=(('m', _('Male')), ('f', _('Female'))))

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prisons_and_regions = get_prisons_and_regions(self.client, request.session)
        self['prison'].field.choices = prisons_and_regions['prisons']
        self['prison_region'].field.choices = prisons_and_regions['regions']

    def get_api_endpoint(self):
        return self.client.credits.prisoners


class UnknownSendersForm(SecurityForm):
    def get_api_endpoint(self):
        return self.client.credits


class CreditsForm(SecurityForm):
    def get_api_endpoint(self):
        return self.client.credits
