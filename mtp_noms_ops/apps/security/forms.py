import collections
import enum
from math import ceil
import re
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth.api_client import get_connection

from mtp_noms_ops.utils import make_page_range


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


def insert_blank_option(choices, title=_('Select an option')):
    new_choices = [('', title)]
    new_choices.extend(choices)
    return new_choices


def validate_amount(amount):
    if not re.match(r'^£?\d+(\.\d\d)?$', amount):
        raise ValidationError(_('Invalid amount'), code='invalid')


def validate_prisoner_number(prisoner_number):
    if not re.match(r'^[a-z]\d\d\d\d[a-z]{2}$', prisoner_number, flags=re.I):
        raise ValidationError(_('Invalid prisoner number'), code='invalid')


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
    received_at_0 = forms.DateField(label=_('Received since'), help_text=_('eg 01/06/2016'), required=False)
    received_at_1 = forms.DateField(label=_('Received before'), help_text=_('eg 01/06/2016'), required=False)

    extra_filters = {}

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
            if value is None or isinstance(value, str) and len(value) == 0:
                continue
            data[field.name] = value
        return data

    def get_object_list(self):
        end_point = self.get_api_endpoint()
        page = self.cleaned_data['page']
        offset = (page - 1) * self.page_size
        filters = self.get_query_data()
        filters.update(self.extra_filters)
        data = end_point.get(offset=offset, limit=self.page_size, **filters)
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
                                     ('-prisoner_count', _('Number of prisoners (high to low)')),
                                     ('-credit_count', _('Number of payments (high to low)')),
                                     ('-credit_total', _('Total sent (high to low)')),
                                     ('sender_name', _('Sender name (A to Z)')),
                                 ])

    prisoner_count_0 = forms.IntegerField(label=_('Minimum prisoners sent to'), required=False, min_value=1)
    prisoner_count_1 = forms.IntegerField(label=_('Maximum prisoners sent to'), required=False, min_value=1)
    credit_count_0 = forms.IntegerField(label=_('Minimum credits sent'), required=False, min_value=1)
    credit_count_1 = forms.IntegerField(label=_('Maximum credits sent'), required=False, min_value=1)
    credit_total_0 = forms.IntegerField(label=_('Minimum total sent'), required=False)
    credit_total_1 = forms.IntegerField(label=_('Maximum total sent'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'),
    #                          required=False)

    sender_name = forms.CharField(label=_('Sender name'), required=False)
    sender_sort_code = forms.CharField(label=_('Sender sort code'), help_text=_('eg 01-23-45'), required=False)
    sender_account_number = forms.CharField(label=_('Sender account number'), required=False)
    sender_roll_number = forms.CharField(label=_('Sender roll number'), required=False)

    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_gender = forms.ChoiceField(label=_('Prisoner gender'), required=False,
                                      choices=(('m', _('Male')), ('f', _('Female'))))

    extra_filters = {
        'include_invalid': 'True'
    }

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prisons_and_regions = get_prisons_and_regions(self.client, request.session)
        self['prison'].field.choices = insert_blank_option(prisons_and_regions['prisons'],
                                                           title=_('All prisons'))
        self['prison_region'].field.choices = insert_blank_option(prisons_and_regions['regions'],
                                                                  title=_('All regions'))

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
                                     ('-sender_count', _('Number of senders (high to low)')),
                                     ('-credit_count', _('Number of payments (high to low)')),
                                     ('-credit_total', _('Total received (high to low)')),
                                     ('prisoner_name', _('Prisoner name (A to Z)')),
                                     ('prisoner_number', _('Prisoner number (A to Z)')),
                                 ])

    sender_count_0 = forms.IntegerField(label=_('Minimum senders received from'), required=False, min_value=1)
    sender_count_1 = forms.IntegerField(label=_('Maximum senders received from'), required=False, min_value=1)
    credit_count_0 = forms.IntegerField(label=_('Minimum credits received'), required=False, min_value=1)
    credit_count_1 = forms.IntegerField(label=_('Maximum credits received'), required=False, min_value=1)
    credit_total_0 = forms.IntegerField(label=_('Minimum total received'), required=False)
    credit_total_1 = forms.IntegerField(label=_('Maximum total received'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'),
    #                          required=False)

    prisoner_number = forms.CharField(label=_('Prisoner number'), validators=[validate_prisoner_number], required=False)
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)

    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_gender = forms.ChoiceField(label=_('Prisoner gender'), required=False,
                                      choices=(('m', _('Male')), ('f', _('Female'))))

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prisons_and_regions = get_prisons_and_regions(self.client, request.session)
        self['prison'].field.choices = insert_blank_option(prisons_and_regions['prisons'],
                                                           title=_('All prisons'))
        self['prison_region'].field.choices = insert_blank_option(prisons_and_regions['regions'],
                                                                  title=_('All regions'))

    def get_api_endpoint(self):
        return self.client.credits.prisoners


class AmountPattern(enum.Enum):
    not_integral = _('Non-integer amount')
    not_multiple_5 = _('Not a multiple of £5')
    not_multiple_10 = _('Not a multiple of £10')
    gte_100 = _('£100 or more')
    exact = _('Exact amount')
    pence = _('Exact pence part')

    @classmethod
    def get_choices(cls):
        return [(choice.name, choice.value) for choice in cls]

    @classmethod
    def update_query_data(cls, query_data):
        amount_pattern = query_data.pop('amount_pattern', None)
        try:
            amount_pattern = cls[amount_pattern]
        except KeyError:
            return

        amount_exact = query_data.pop('amount_exact', None)
        amount_pence = query_data.pop('amount_pence', None)

        if amount_pattern == cls.not_integral:
            query_data['exclude_amount__endswith'] = '00'
        elif amount_pattern == cls.not_multiple_5:
            query_data['exclude_amount__regex'] = '(500|000)$'
        elif amount_pattern == cls.not_multiple_10:
            query_data['exclude_amount__endswith'] = '000'
        elif amount_pattern == cls.gte_100:
            query_data['amount__gte'] = '10000'
        elif amount_pattern == cls.exact:
            query_data['amount'] = amount_exact
        elif amount_pattern == cls.pence:
            query_data['amount__endswith'] = '%02d' % amount_pence
        else:
            raise NotImplementedError


class CreditsForm(SecurityForm):
    ordering = forms.ChoiceField(label=_('Sort by'), required=False,
                                 initial='-received_at',
                                 choices=[
                                     ('-received_at', _('Received date (newest to oldest)')),
                                     ('-amount', _('Amount sent (high to low)')),
                                     ('prisoner_name', _('Prisoner name (A to Z)')),
                                     ('prisoner_number', _('Prisoner number (A to Z)')),
                                 ])

    amount_pattern = forms.ChoiceField(label=_('Amount (£)'), required=False,
                                       choices=insert_blank_option(AmountPattern.get_choices(), _('Any amount')))
    amount_exact = forms.CharField(label=AmountPattern.exact.value, validators=[validate_amount], required=False)
    amount_pence = forms.IntegerField(label=AmountPattern.pence.value, min_value=0, max_value=99, required=False)

    prisoner_number = forms.CharField(label=_('Prisoner number'), validators=[validate_prisoner_number], required=False)
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)
    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_gender = forms.ChoiceField(label=_('Prisoner gender'), required=False,
                                      choices=[('m', _('Male')), ('f', _('Female'))])

    sender_name = forms.CharField(label=_('Sender name'), required=False)
    sender_sort_code = forms.CharField(label=_('Sender sort code'), help_text=_('eg 01-23-45'), required=False)
    sender_account_number = forms.CharField(label=_('Sender account number'), required=False)
    sender_roll_number = forms.CharField(label=_('Sender roll number'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'),
    #                          required=False)

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prisons_and_regions = get_prisons_and_regions(self.client, request.session)
        self['prison'].field.choices = insert_blank_option(prisons_and_regions['prisons'],
                                                           title=_('All prisons'))
        self['prison_region'].field.choices = insert_blank_option(prisons_and_regions['regions'],
                                                                  title=_('All regions'))

    def clean_amount_exact(self):
        amount_exact = self.cleaned_data.get('amount_exact')
        if amount_exact:
            amount_exact = amount_exact.lstrip('£')
            if '.' in amount_exact:
                amount_exact = amount_exact.replace('.', '')
            else:
                amount_exact += '00'
        elif self.cleaned_data.get('amount_pattern') == 'exact':
            raise ValidationError(_('This field is required for the selected amount pattern'),
                                  code='required')
        return amount_exact

    def clean_amount_pence(self):
        amount_pence = self.cleaned_data.get('amount_pence')
        if amount_pence is None and self.cleaned_data.get('amount_pattern') == 'pence':
            raise ValidationError(_('This field is required for the selected amount pattern'),
                                  code='required')
        return amount_pence

    def clean_prisoner_number(self):
        prisoner_number = self.cleaned_data.get('prisoner_number')
        if prisoner_number:
            return prisoner_number.upper()
        return prisoner_number

    def clean_sender_sort_code(self):
        sender_sort_code = self.cleaned_data.get('sender_sort_code')
        if sender_sort_code:
            sender_sort_code = sender_sort_code.replace('-', '')
        return sender_sort_code

    def get_api_endpoint(self):
        return self.client.credits

    def get_query_data(self):
        query_data = super().get_query_data()
        AmountPattern.update_query_data(query_data)
        return query_data
