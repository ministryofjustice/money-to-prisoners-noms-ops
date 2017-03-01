import collections
from datetime import datetime, time, timedelta
import enum
from math import ceil
import re
from urllib.parse import urlencode, urlparse

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils.dateformat import format as date_format
from django.utils.html import format_html, format_html_join
from django.utils.timezone import now, utc
from django.utils.translation import gettext_lazy as _, override as override_locale
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.api import retrieve_all_pages
from mtp_common.auth.api_client import get_connection
from slumber.exceptions import HttpNotFoundError, SlumberHttpBaseException

from security.models import PrisonList
from security.searches import (
    save_search, update_result_count, delete_search, get_existing_search
)
from security.templatetags.security import currency as format_currency


def get_credit_source_choices(blank_option=_('Any method')):
    return insert_blank_option(
        [('bank_transfer', _('Bank transfer')), ('online', _('Debit card'))],
        title=blank_option
    )


def insert_blank_option(choices, title=_('Select an option')):
    new_choices = [('', title)]
    new_choices.extend(choices)
    return new_choices


def parse_amount(value, as_int=True):
    # assumes a valid amount in pounds, i.e. validate_amount passes
    value = value.lstrip('£')
    if '.' in value:
        value = value.replace('.', '')
    else:
        value += '00'
    if as_int:
        return int(value)
    return value


def validate_amount(amount):
    if not re.match(r'^£?\d+(\.\d\d)?$', amount):
        raise ValidationError(_('Invalid amount'), code='invalid')


def validate_prisoner_number(prisoner_number):
    if not re.match(r'^[a-z]\d\d\d\d[a-z]{2}$', prisoner_number, flags=re.I):
        raise ValidationError(_('Invalid prisoner number'), code='invalid')


def validate_range_field(field_name, bound_ordering_msg):
    def inner(cls):
        lower = field_name + '__gte'
        upper = field_name + '__lte'

        base_clean = cls.clean

        def clean(self):
            base_clean(self)
            lower_value = self.cleaned_data.get(lower)
            upper_value = self.cleaned_data.get(upper)
            if lower_value is not None and upper_value is not None and lower_value > upper_value:
                self.add_error(upper, ValidationError(bound_ordering_msg or _('Must be greater than the lower bound'),
                                                      code='bound_ordering'))
            return self.cleaned_data

        setattr(cls, 'clean', clean)
        return cls

    return inner


class SecurityForm(GARequestErrorReportingMixin, forms.Form):
    """
    Base form for security searches
    """
    page = forms.IntegerField(min_value=1)
    page_size = 20

    exclusive_date_params = []

    filtered_description_template = NotImplemented
    unfiltered_description_template = NotImplemented
    description_templates = ()
    description_capitalisation = {}

    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request
        self.client = get_connection(request)
        self.page_count = 0

    def clean_ordering(self):
        return self.cleaned_data['ordering'] or self.fields['ordering'].initial

    def clean(self):
        self.cleaned_data['object_list'] = self.get_object_list()
        return self.cleaned_data

    def get_object_list_endpoint(self):
        raise NotImplementedError

    def get_query_data(self, allow_parameter_manipulation=True):
        """
        Serialises the form into a dictionary stripping empty and pagination fields.
        NB: Forms can sometimes manipulate parameters so this is not always reversible.
        :param allow_parameter_manipulation: turn off to make serialisation reversible
        :return: collections.OrderedDict
        """
        data = collections.OrderedDict()
        for field in self:
            if field.name == 'page':
                continue
            value = self.cleaned_data.get(field.name)
            if value in [None, '', []]:
                continue
            data[field.name] = value
        return data

    def get_object_list(self):
        """
        Gets the security object list: senders, prisoners or credits
        :return: list
        """
        page = self.cleaned_data.get('page')
        if not page:
            return []
        offset = (page - 1) * self.page_size
        filters = self.get_query_data()
        for param in filters:
            if param in self.exclusive_date_params:
                filters[param] += timedelta(days=1)
        try:
            data = self.get_object_list_endpoint().get(offset=offset, limit=self.page_size, **filters)
        except SlumberHttpBaseException:
            self.add_error(None, _('This service is currently unavailable'))
            return []
        count = data.get('count', 0)
        self.total_count = count
        self.page_count = int(ceil(count / self.page_size))
        return data.get('results', [])

    def get_complete_object_list(self):
        filters = self.get_query_data()
        return retrieve_all_pages(self.get_object_list_endpoint().get, **filters)

    @cached_property
    def query_string(self):
        return urlencode(self.get_query_data(allow_parameter_manipulation=False), doseq=True)

    def _get_value_text(self, bf):
        f = bf.field
        v = self.cleaned_data.get(bf.name) or f.initial
        if isinstance(f, forms.ChoiceField):
            v = dict(f.choices).get(v)
            if not v:
                return None
            v = str(v)
            capitalisation = self.description_capitalisation.get(bf.name)
            if capitalisation == 'preserve':
                return v
            if capitalisation == 'lowerfirst':
                return v[0].lower() + v[1:]
            return v.lower()
        if isinstance(f, forms.DateField) and v is not None:
            return date_format(v, 'j M Y')
        if isinstance(f, forms.IntegerField) and v is not None:
            return str(v)
        return v or None

    @property
    def search_description(self):
        with override_locale(settings.LANGUAGE_CODE):
            description_kwargs = {
                'ordering_description': self._get_value_text(self['ordering']),
            }

            filters = {}
            for bound_field in self:
                if bound_field.name in ('page', 'ordering'):
                    continue
                description_override = 'describe_field_%s' % bound_field.name
                if hasattr(self, description_override):
                    value = getattr(self, description_override)()
                else:
                    value = self._get_value_text(bound_field)
                if value is None:
                    continue
                filters[bound_field.name] = format_html('<strong>{}</strong>', value)
            if any(field in filters for field in ('prisoner_number', 'prisoner_name')):
                filters['prison_preposition'] = 'in'
            else:
                filters['prison_preposition'] = 'to'

            descriptions = []
            for template_group in self.description_templates:
                for filter_template in template_group:
                    try:
                        descriptions.append(format_html(filter_template, **filters))
                        break
                    except KeyError:
                        continue

            if descriptions:
                description_template = self.filtered_description_template
                if len(descriptions) > 1:
                    all_but_last = format_html_join(', ', '{}', ((d,) for d in descriptions[:-1]))
                    filter_description = format_html('{0} and {1}', all_but_last, descriptions[-1])
                else:
                    filter_description = descriptions[0]
                description_kwargs['filter_description'] = filter_description
                has_filters = True
            else:
                description_template = self.unfiltered_description_template
                has_filters = False

            return {
                'has_filters': has_filters,
                'description': format_html(description_template, **description_kwargs),
            }

    def check_and_update_saved_searches(self, page_title):
        site_url = '?'.join([urlparse(self.request.path).path, self.query_string])
        self.existing_search = get_existing_search(self.client, site_url)
        if self.existing_search:
            update_result_count(
                self.client, self.existing_search['id'], self.total_count
            )
        if self.request.GET.get('pin') and not self.existing_search:
            endpoint = self.get_object_list_endpoint()
            endpoint_path = urlparse(endpoint.url()).path
            self.existing_search = save_search(
                self.client, page_title, endpoint_path, site_url,
                filters=self.get_query_data(), last_result_count=self.total_count
            )
        elif self.request.GET.get('unpin') and self.existing_search:
            delete_search(self.client, self.existing_search['id'])
            self.existing_search = None


@validate_range_field('prisoner_count', _('Must be larger than the minimum prisoners'))
@validate_range_field('credit_count', _('Must be larger than the minimum credits'))
@validate_range_field('credit_total', _('Must be larger than the minimum total'))
class SendersForm(SecurityForm):
    ordering = forms.ChoiceField(label=_('Order by'), required=False,
                                 initial='-prisoner_count',
                                 choices=[
                                     ('prisoner_count', _('Number of prisoners (low to high)')),
                                     ('-prisoner_count', _('Number of prisoners (high to low)')),
                                     ('prison_count', _('Number of prisons (low to high)')),
                                     ('-prison_count', _('Number of prisons (high to low)')),
                                     ('credit_count', _('Number of credits (low to high)')),
                                     ('-credit_count', _('Number of credits (high to low)')),
                                     ('credit_total', _('Total sent (low to high)')),
                                     ('-credit_total', _('Total sent (high to low)')),
                                 ])

    prisoner_count__gte = forms.IntegerField(label=_('Number of prisoners (minimum)'), required=False, min_value=1)
    prisoner_count__lte = forms.IntegerField(label=_('Maximum prisoners sent to'), required=False, min_value=1)
    prison_count__gte = forms.IntegerField(label=_('Number of prisons (minimum)'), required=False, min_value=1)
    prison_count__lte = forms.IntegerField(label=_('Maximum prisons sent to'), required=False, min_value=1)
    credit_count__gte = forms.IntegerField(label=_('Minimum credits sent'), required=False, min_value=1)
    credit_count__lte = forms.IntegerField(label=_('Maximum credits sent'), required=False, min_value=1)
    credit_total__gte = forms.IntegerField(label=_('Minimum total sent'), required=False)
    credit_total__lte = forms.IntegerField(label=_('Maximum total sent'), required=False)

    sender_name = forms.CharField(label=_('Sender name'), required=False)
    source = forms.ChoiceField(label=_('Payment method'), required=False, choices=get_credit_source_choices())
    sender_sort_code = forms.CharField(label=_('Sender sort code'), help_text=_('for example 01-23-45'), required=False)
    sender_account_number = forms.CharField(label=_('Sender account number'), required=False)
    sender_roll_number = forms.CharField(label=_('Sender roll number'), required=False)
    card_number_last_digits = forms.CharField(label=_('Last 4 digits of card number'), max_length=4, required=False)
    sender_email = forms.CharField(label=_('Sender email'), required=False)

    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'), required=False)

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Showing senders who {filter_description}, ordered by {ordering_description}.'
    unfiltered_description_template = 'Showing all senders ordered by {ordering_description}.'
    description_templates = (
        ('are named ‘{sender_name}’',),
        ('have email {sender_email}',),
        ('sent by {source} from account {sender_account_number} {sender_sort_code}',
         'sent by {source} from account {sender_account_number}',
         'sent by {source} from sort code {sender_sort_code}',
         'sent by {source} **** **** **** {card_number_last_digits}',
         'sent by {source}',),
        ('sent to {prison}',),
        ('sent to {prison_population} {prison_category} prisons in {prison_region}',
         'sent to {prison_category} prisons in {prison_region}',
         'sent to {prison_population} prisons in {prison_region}',
         'sent to {prison_population} {prison_category} prisons',
         'sent to {prison_category} prisons',
         'sent to {prison_population} prisons',
         'sent to prisons in {prison_region}',),
        ('sent to {prisoner_count__gte}-{prisoner_count__lte} prisoners',
         'sent to at least {prisoner_count__gte} prisoners',
         'sent to at most {prisoner_count__lte} prisoners',),
        ('sent to {prison_count__gte}-{prison_count__lte} prisons',
         'sent to at least {prison_count__gte} prisons',
         'sent to at most {prison_count__lte} prisons',),
        ('sent between {credit_count__gte}-{credit_count__lte} credits',
         'sent at least {credit_count__gte} credits',
         'sent at most {credit_count__lte} credits',),
        ('sent between £{credit_total__gte}-{credit_total__lte}',
         'sent at least £{credit_total__gte}',
         'sent at most £{credit_total__lte}',),
    )
    description_capitalisation = {
        'ordering': 'lowerfirst',
        'prison': 'preserve',
        'prison_region': 'preserve',
        'prison_category': 'lowerfirst',
    }

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prison_list = PrisonList(self.client)
        self['prison'].field.choices = insert_blank_option(prison_list.prison_choices,
                                                           title=_('All prisons'))
        self['prison_region'].field.choices = insert_blank_option(prison_list.region_choices,
                                                                  title=_('All regions'))
        self['prison_population'].field.choices = insert_blank_option(prison_list.population_choices,
                                                                      title=_('All types'))
        self['prison_category'].field.choices = insert_blank_option(prison_list.category_choices,
                                                                    title=_('All categories'))
        self.prison_list = prison_list

    def clean_sender_sort_code(self):
        if self.cleaned_data.get('source') != 'bank_transfer':
            return ''
        sender_sort_code = self.cleaned_data.get('sender_sort_code')
        if sender_sort_code:
            sender_sort_code = sender_sort_code.replace('-', '')
        return sender_sort_code

    def clean_sender_account_number(self):
        if self.cleaned_data.get('source') != 'bank_transfer':
            return ''
        return self.cleaned_data.get('sender_account_number')

    def clean_sender_roll_number(self):
        if self.cleaned_data.get('source') != 'bank_transfer':
            return ''
        return self.cleaned_data.get('sender_roll_number')

    def clean_card_number_last_digits(self):
        if self.cleaned_data.get('source') != 'online':
            return ''
        return self.cleaned_data.get('card_number_last_digits')

    def get_object_list_endpoint(self):
        return self.client.senders

    def get_query_data(self, allow_parameter_manipulation=True):
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            for field in ('credit_total__gte', 'credit_total__lte'):
                value = query_data.get(field)
                if value is not None:
                    query_data[field] = value * 100
        return query_data


@validate_range_field('sender_count', _('Must be larger than the minimum senders'))
@validate_range_field('credit_count', _('Must be larger than the minimum credits'))
@validate_range_field('credit_total', _('Must be larger than the minimum total'))
class PrisonersForm(SecurityForm):
    ordering = forms.ChoiceField(label=_('Order by'), required=False,
                                 initial='-sender_count',
                                 choices=[
                                     ('sender_count', _('Number of senders (low to high)')),
                                     ('-sender_count', _('Number of senders (high to low)')),
                                     ('credit_count', _('Number of credits (low to high)')),
                                     ('-credit_count', _('Number of credits (high to low)')),
                                     ('credit_total', _('Total received (low to high)')),
                                     ('-credit_total', _('Total received (high to low)')),
                                     ('prisoner_name', _('Prisoner name (A to Z)')),
                                     ('-prisoner_name', _('Prisoner name (Z to A)')),
                                     ('prisoner_number', _('Prisoner number (A to Z)')),
                                     ('-prisoner_number', _('Prisoner number (Z to A)')),
                                 ])

    sender_count__gte = forms.IntegerField(label=_('Number of senders (minimum)'), required=False, min_value=1)
    sender_count__lte = forms.IntegerField(label=_('Maximum senders received from'), required=False, min_value=1)
    credit_count__gte = forms.IntegerField(label=_('Minimum credits received'), required=False, min_value=1)
    credit_count__lte = forms.IntegerField(label=_('Maximum credits received'), required=False, min_value=1)
    credit_total__gte = forms.IntegerField(label=_('Minimum total received'), required=False)
    credit_total__lte = forms.IntegerField(label=_('Maximum total received'), required=False)

    prisoner_number = forms.CharField(label=_('Prisoner number'),
                                      validators=[validate_prisoner_number], required=False)
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)
    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'), required=False)

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Showing prisoners who {filter_description}, ordered by {ordering_description}.'
    unfiltered_description_template = 'Showing all prisoners ordered by {ordering_description}.'
    description_templates = (
        ('are named ‘{prisoner_name}’',),
        ('have prisoner number {prisoner_number}',),
        ('are at {prison}',),
        ('are at {prison_population} {prison_category} prisons in {prison_region}',
         'are at {prison_category} prisons in {prison_region}',
         'are at {prison_population} prisons in {prison_region}',
         'are at {prison_population} {prison_category} prisons',
         'are at {prison_category} prisons',
         'are at {prison_population} prisons',
         'are at prisons in {prison_region}',),
        ('received from {sender_count__gte}-{sender_count__lte} senders',
         'received from at least {sender_count__gte} senders',
         'received from at most {sender_count__lte} senders',),
        ('received between {credit_count__gte}-{credit_count__lte} credits',
         'received at least {credit_count__gte} credits',
         'received at most {credit_count__lte} credits',),
        ('received between £{credit_total__gte}-{credit_total__lte}',
         'received at least £{credit_total__gte}',
         'received at most £{credit_total__lte}',),
    )
    description_capitalisation = {
        'ordering': 'lowerfirst',
        'prison': 'preserve',
        'prison_region': 'preserve',
        'prison_category': 'lowerfirst',
    }

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prison_list = PrisonList(self.client)
        self['prison'].field.choices = insert_blank_option(prison_list.prison_choices,
                                                           title=_('All prisons'))
        self['prison_region'].field.choices = insert_blank_option(prison_list.region_choices,
                                                                  title=_('All regions'))
        self['prison_population'].field.choices = insert_blank_option(prison_list.population_choices,
                                                                      title=_('All types'))
        self['prison_category'].field.choices = insert_blank_option(prison_list.category_choices,
                                                                    title=_('All categories'))
        self.prison_list = prison_list

    def get_object_list_endpoint(self):
        return self.client.prisoners

    def get_query_data(self, allow_parameter_manipulation=True):
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            for field in ('credit_total__gte', 'credit_total__lte'):
                value = query_data.get(field)
                if value is not None:
                    query_data[field] = value * 100
        return query_data


class AmountPattern(enum.Enum):
    not_integral = _('Not a whole number')
    not_multiple_5 = _('Not a multiple of £5')
    not_multiple_10 = _('Not a multiple of £10')
    gte_100 = _('£100 or more')
    exact = _('Exact amount')
    pence = _('Exact number of pence')

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
            query_data['amount'] = parse_amount(amount_exact, as_int=False)
        elif amount_pattern == cls.pence:
            query_data['amount__endswith'] = '%02d' % amount_pence
        else:
            raise NotImplementedError


@validate_range_field('received_at', _('Must be after the start date'))
class CreditsForm(SecurityForm):
    ordering = forms.ChoiceField(label=_('Order by'), required=False,
                                 initial='-received_at',
                                 choices=[
                                     ('received_at', _('Received date (oldest to newest)')),
                                     ('-received_at', _('Received date (newest to oldest)')),
                                     ('amount', _('Amount sent (low to high)')),
                                     ('-amount', _('Amount sent (high to low)')),
                                     ('prisoner_name', _('Prisoner name (A to Z)')),
                                     ('-prisoner_name', _('Prisoner name (Z to A)')),
                                     ('prisoner_number', _('Prisoner number (A to Z)')),
                                     ('-prisoner_number', _('Prisoner number (Z to A)')),
                                 ])

    received_at__gte = forms.DateField(label=_('Received from'), help_text=_('for example 01/06/2016'), required=False)
    received_at__lt = forms.DateField(label=_('Received to'), help_text=_('for example 01/06/2016'), required=False)

    amount_pattern = forms.ChoiceField(label=_('Amount (£)'), required=False,
                                       choices=insert_blank_option(AmountPattern.get_choices(), _('Any amount')))
    amount_exact = forms.CharField(label=AmountPattern.exact.value, validators=[validate_amount], required=False)
    amount_pence = forms.IntegerField(label=AmountPattern.pence.value, min_value=0, max_value=99, required=False)

    prisoner_number = forms.CharField(label=_('Prisoner number'), validators=[validate_prisoner_number], required=False)
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)
    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

    sender_name = forms.CharField(label=_('Sender name'), required=False)
    source = forms.ChoiceField(label=_('Payment method'), required=False, choices=get_credit_source_choices())
    sender_sort_code = forms.CharField(label=_('Sender sort code'), help_text=_('for example 01-23-45'), required=False)
    sender_account_number = forms.CharField(label=_('Sender account number'), required=False)
    sender_roll_number = forms.CharField(label=_('Sender roll number'), required=False)
    card_number_last_digits = forms.CharField(label=_('Last 4 digits of card number'), max_length=4, required=False)
    sender_email = forms.CharField(label=_('Sender email'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'), required=False)

    exclusive_date_params = ['received_at__lt']

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Showing credits sent {filter_description}, ordered by {ordering_description}.'
    unfiltered_description_template = 'Showing all credits ordered by {ordering_description}.'
    description_templates = (
        ('between {received_at__gte} and {received_at__lt}',
         'since {received_at__gte}',
         'before {received_at__lt}',),
        ('that are {amount_pattern}',),
        ('by ‘{sender_name}’ with email {sender_email}',
         'by {sender_email}',
         'by ‘{sender_name}’',),
        ('by {source} from account {sender_account_number} {sender_sort_code}',
         'by {source} from account {sender_account_number}',
         'by {source} from sort code {sender_sort_code}',
         'by {source} **** **** **** {card_number_last_digits}',
         'by {source}',),
        ('to prisoner {prisoner_name} ({prisoner_number})',
         'to prisoners named ‘{prisoner_name}’',
         'to prisoner {prisoner_number}',),
        ('{prison_preposition} {prison}',),
        ('{prison_preposition} {prison_population} {prison_category} prisons in {prison_region}',
         '{prison_preposition} {prison_category} prisons in {prison_region}',
         '{prison_preposition} {prison_population} prisons in {prison_region}',
         '{prison_preposition} {prison_population} {prison_category} prisons',
         '{prison_preposition} {prison_category} prisons',
         '{prison_preposition} {prison_population} prisons',
         '{prison_preposition} prisons in {prison_region}',),
    )
    description_capitalisation = {
        'ordering': 'lowerfirst',
        'prison': 'preserve',
        'prison_region': 'preserve',
        'prison_category': 'lowerfirst',
    }

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prison_list = PrisonList(self.client)
        self['prison'].field.choices = insert_blank_option(prison_list.prison_choices,
                                                           title=_('All prisons'))
        self['prison_region'].field.choices = insert_blank_option(prison_list.region_choices,
                                                                  title=_('All regions'))
        self['prison_population'].field.choices = insert_blank_option(prison_list.population_choices,
                                                                      title=_('All types'))
        self['prison_category'].field.choices = insert_blank_option(prison_list.category_choices,
                                                                    title=_('All categories'))
        self.prison_list = prison_list

    def clean_amount_exact(self):
        if self.cleaned_data.get('amount_pattern') != 'exact':
            return ''
        amount = self.cleaned_data.get('amount_exact')
        if amount is None:
            raise ValidationError(_('This field is required for the selected amount pattern'), code='required')
        return amount

    def clean_amount_pence(self):
        if self.cleaned_data.get('amount_pattern') != 'pence':
            return None
        amount = self.cleaned_data.get('amount_pence')
        if amount is None:
            raise ValidationError(_('This field is required for the selected amount pattern'), code='required')
        return amount

    def clean_prisoner_number(self):
        prisoner_number = self.cleaned_data.get('prisoner_number')
        if prisoner_number:
            return prisoner_number.upper()
        return prisoner_number

    def clean_sender_sort_code(self):
        if self.cleaned_data.get('source') != 'bank_transfer':
            return ''
        sender_sort_code = self.cleaned_data.get('sender_sort_code')
        if sender_sort_code:
            sender_sort_code = sender_sort_code.replace('-', '')
        return sender_sort_code

    def clean_sender_account_number(self):
        if self.cleaned_data.get('source') != 'bank_transfer':
            return ''
        return self.cleaned_data.get('sender_account_number')

    def clean_sender_roll_number(self):
        if self.cleaned_data.get('source') != 'bank_transfer':
            return ''
        return self.cleaned_data.get('sender_roll_number')

    def clean_card_number_last_digits(self):
        if self.cleaned_data.get('source') != 'online':
            return ''
        return self.cleaned_data.get('card_number_last_digits')

    def get_object_list_endpoint(self):
        return self.client.credits

    def get_query_data(self, allow_parameter_manipulation=True):
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            AmountPattern.update_query_data(query_data)
        return query_data

    def describe_field_amount_pattern(self):
        value = self.cleaned_data.get('amount_pattern')
        if not value:
            return None
        if value in ('exact', 'pence'):
            amount_value = self.cleaned_data.get('amount_%s' % value)
            if amount_value is None:
                return None
            if value == 'exact':
                return format_currency(parse_amount(amount_value))
            return _('ending in %02d pence') % amount_value
        description = dict(self['amount_pattern'].field.choices).get(value)
        return str(description).lower() if description else None


class SecurityDetailForm(SecurityForm):
    def __init__(self, object_id, **kwargs):
        super().__init__(**kwargs)
        self.object_id = object_id

    def clean(self):
        self.cleaned_data['object'] = self.get_object()
        return super().clean()

    def get_object_list_endpoint(self):
        return self.get_object_endpoint().credits

    def get_object_endpoint(self):
        raise NotImplementedError

    def get_object(self):
        """
        Gets the security detail object, a sender or prisoner profile
        :return: dict or None if not found
        """
        try:
            return self.get_object_endpoint().get()
        except HttpNotFoundError:
            self.add_error(None, _('Not found'))
            return None
        except SlumberHttpBaseException:
            self.add_error(None, _('This service is currently unavailable'))
            return {}


class SendersDetailForm(SecurityDetailForm):
    ordering = forms.ChoiceField(label=_('Order by'), required=False,
                                 initial='-received_at',
                                 choices=[
                                     ('received_at', _('Received date (oldest to newest)')),
                                     ('-received_at', _('Received date (newest to oldest)')),
                                     ('amount', _('Amount sent (low to high)')),
                                     ('-amount', _('Amount sent (high to low)')),
                                     ('prisoner_name', _('Prisoner name (A to Z)')),
                                     ('-prisoner_name', _('Prisoner name (Z to A)')),
                                     ('prisoner_number', _('Prisoner number (A to Z)')),
                                     ('-prisoner_number', _('Prisoner number (Z to A)')),
                                 ])

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Showing credits sent by this sender that {filter_description}, ' \
                                    'ordered by {ordering_description}.'
    unfiltered_description_template = 'Showing all credits sent by this sender ordered by {ordering_description}.'

    def get_object_endpoint(self):
        return self.client.senders(self.object_id)


class PrisonersDetailForm(SecurityDetailForm):
    ordering = forms.ChoiceField(label=_('Order by'), required=False,
                                 initial='-received_at',
                                 choices=[
                                     ('received_at', _('Received date (oldest to newest)')),
                                     ('-received_at', _('Received date (newest to oldest)')),
                                     ('amount', _('Amount sent (low to high)')),
                                     ('-amount', _('Amount sent (high to low)')),
                                 ])

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Showing credits received by this prisoner that {filter_description}, ' \
                                    'ordered by {ordering_description}.'
    unfiltered_description_template = 'Showing all credits received by this prisoner ordered by {ordering_description}.'

    def get_object_endpoint(self):
        return self.client.prisoners(self.object_id)


class ReviewCreditsForm(GARequestErrorReportingMixin, forms.Form):
    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.client = get_connection(request)

        for credit in self.credits:
            self.fields['comment_%s' % credit['id']] = forms.CharField(required=False)

    @cached_property
    def credits(self):
        prisons = [
            prison['nomis_id']
            for prison in self.request.user.user_data.get('prisons', [])
            if prison['pre_approval_required']
        ]
        return retrieve_all_pages(
            self.client.credits.get, valid=True, reviewed=False, prison=prisons, resolution='pending',
            received_at__lt=datetime.combine(now().date(), time(0, 0, 0, tzinfo=utc))
        )

    def review(self):
        reviewed = set()
        comments = []
        for credit in self.credits:
            reviewed.add(credit['id'])
            comment = self.cleaned_data['comment_%s' % credit['id']]

            if comment:
                comments.append({
                    'credit': credit['id'],
                    'comment': comment
                })
        if comments:
            self.client.credits.comments.post(comments)
        self.client.credits.actions.review.post({
            'credit_ids': list(reviewed)
        })

        return len(reviewed)
