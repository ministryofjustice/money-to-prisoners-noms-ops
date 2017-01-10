import collections
from datetime import datetime, time, timedelta
import enum
from functools import reduce
from math import ceil
import re
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils.dateformat import format as date_format
from django.utils.html import format_html, format_html_join
from django.utils.timezone import now, utc
from django.utils.translation import gettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.api import retrieve_all_pages
from mtp_common.auth.api_client import get_connection


def sorted_prison_type_choices(type_list):
    def flatten(nested_list):
        return reduce(lambda a, b: a + b, nested_list, [])

    def exclude_duplicate_dicts(dict_list):
        return {d['name']: d for d in dict_list}.values()

    return sorted(
        exclude_duplicate_dicts(flatten(type_list)), key=lambda d: d['name']
    )


def get_prison_details_choices(client):
    prisons = retrieve_all_pages(client.prisons.get)
    prison_choices = [
        (prison['nomis_id'], prison['name'])
        for prison in sorted(prisons, key=lambda prison: prison['name'])
    ]
    region_choices = [
        (region, region)
        for region in sorted(set(prison['region'] for prison in prisons if prison['region']))
    ]
    population_choices = [
        (population['name'], population['description'])
        for population in sorted_prison_type_choices(prison['populations'] for prison in prisons)
    ]
    category_choices = [
        (category['name'], category['description'])
        for category in sorted_prison_type_choices(prison['categories'] for prison in prisons)
    ]
    return {
        'prisons': prison_choices,
        'regions': region_choices,
        'populations': population_choices,
        'categories': category_choices,
    }


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
        lower = field_name + '__gte'
        upper = field_name + '__lte'

        base_clean = cls.clean

        def clean(self):
            base_clean(self)
            lower_value = self.cleaned_data.get(lower)
            upper_value = self.cleaned_data.get(upper)
            if lower_value and upper_value and lower_value > upper_value:
                self.add_error(
                    upper,
                    ValidationError(bound_ordering_msg or _('Must be greater than the lower bound'),
                                    code='bound_ordering'))
            return self.cleaned_data

        setattr(cls, 'clean', clean)
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

    extra_filters = {}
    exclusive_date_params = []

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
            if value in [None, '', []]:
                continue
            data[field.name] = value
        return data

    def get_object_list(self):
        end_point = self.get_api_endpoint()
        page = self.cleaned_data['page']
        offset = (page - 1) * self.page_size
        filters = self.get_query_data()
        for param in filters:
            if param in self.exclusive_date_params:
                filters[param] += timedelta(days=1)
        filters.update(self.extra_filters)
        data = end_point.get(offset=offset, limit=self.page_size, **filters)
        count = data['count']
        self.page_count = int(ceil(count / self.page_size))
        return data.get('results', [])

    def get_complete_object_list(self):
        filters = self.get_query_data()
        filters.update(self.extra_filters)
        return retrieve_all_pages(self.get_api_endpoint().get, **filters)

    @cached_property
    def query_string(self):
        return urlencode(self.get_query_data(), doseq=True)

    @property
    def search_description(self):
        def get_value_text(bf):
            f = bf.field
            v = self.cleaned_data.get(bf.name) or f.initial
            if isinstance(f, forms.ChoiceField):
                return dict(f.choices).get(v)
            if isinstance(f, forms.DateField) and v is not None:
                return date_format(v, 'j M Y')
            if isinstance(f, forms.IntegerField) and v is not None:
                return str(v)
            return v or None

        filters = []
        for bound_field in self:
            if bound_field.name in ('page', 'ordering'):
                continue
            value = get_value_text(bound_field)
            if value is None:
                continue
            filters.append((str(bound_field.label).lower(), value))
        if filters:
            filters = format_html_join(', ', _('{} is <strong>{}</strong>'), filters)
            description = format_html(_('Filtering results: {}.'), filters)
        else:
            description = _('Showing all results.')

        ordering = get_value_text(self['ordering'])
        if ordering:
            return format_html('{} {}', description, _('Ordered by %s.') % str(ordering).lower())
        return description


@validate_range_field('prisoner_count', _('Must be larger than the minimum prisoners'))
@validate_range_field('credit_count', _('Must be larger than the minimum credits'))
@validate_range_field('credit_total', _('Must be larger than the minimum total'))
class SendersForm(SecurityForm):
    ordering = forms.ChoiceField(label=_('Sort by'), required=False,
                                 initial='-prisoner_count',
                                 choices=[
                                     ('-prisoner_count', _('Number of prisoners (high to low)')),
                                     ('-credit_count', _('Number of credits (high to low)')),
                                     ('-credit_total', _('Total sent (high to low)')),
                                     ('sender_name', _('Sender name (A to Z)')),
                                 ])

    prisoner_count__gte = forms.IntegerField(label=_('Number of prisoners (minimum)'), required=False, min_value=1)
    prisoner_count__lte = forms.IntegerField(label=_('Maximum prisoners sent to'), required=False, min_value=1)
    credit_count__gte = forms.IntegerField(label=_('Minimum credits sent'), required=False, min_value=1)
    credit_count__lte = forms.IntegerField(label=_('Maximum credits sent'), required=False, min_value=1)
    credit_total__gte = forms.IntegerField(label=_('Minimum total sent'), required=False)
    credit_total__lte = forms.IntegerField(label=_('Maximum total sent'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'),
    #                          required=False)

    sender_name = forms.CharField(label=_('Sender name'), required=False)
    sender_sort_code = forms.CharField(label=_('Sender sort code'), help_text=_('eg 01-23-45'), required=False)
    sender_account_number = forms.CharField(label=_('Sender account number'), required=False)
    sender_roll_number = forms.CharField(label=_('Sender roll number'), required=False)
    card_number_last_digits = forms.CharField(label=_('Last 4 digits of card number'), max_length=4, required=False)
    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

    extra_filters = {
        'include_invalid': 'True'
    }

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prison_details_choices = get_prison_details_choices(self.client)
        self['prison'].field.choices = insert_blank_option(prison_details_choices['prisons'],
                                                           title=_('All prisons'))
        self['prison_region'].field.choices = insert_blank_option(prison_details_choices['regions'],
                                                                  title=_('All regions'))
        self['prison_population'].field.choices = insert_blank_option(prison_details_choices['populations'],
                                                                      title=_('All types'))
        self['prison_category'].field.choices = prison_details_choices['categories']

    def clean_sender_sort_code(self):
        sender_sort_code = self.cleaned_data.get('sender_sort_code')
        if sender_sort_code:
            sender_sort_code = sender_sort_code.replace('-', '')
        return sender_sort_code

    def clean_credit_total__gte(self):
        credit_total__gte = self.cleaned_data.get('credit_total__gte')
        if credit_total__gte:
            return int(credit_total__gte*100)
        else:
            return credit_total__gte

    def clean_credit_total__lte(self):
        credit_total__lte = self.cleaned_data.get('credit_total__lte')
        if credit_total__lte:
            return int(credit_total__lte*100)
        else:
            return credit_total__lte

    def get_api_endpoint(self):
        return self.client.senders


@validate_range_field('sender_count', _('Must be larger than the minimum senders'))
@validate_range_field('credit_count', _('Must be larger than the minimum credits'))
@validate_range_field('credit_total', _('Must be larger than the minimum total'))
class PrisonersForm(SecurityForm):
    ordering = forms.ChoiceField(label=_('Sort by'), required=False,
                                 initial='-sender_count',
                                 choices=[
                                     ('-sender_count', _('Number of senders (high to low)')),
                                     ('-credit_count', _('Number of credits (high to low)')),
                                     ('-credit_total', _('Total received (high to low)')),
                                     ('prisoner_name', _('Prisoner name (A to Z)')),
                                     ('prisoner_number', _('Prisoner number (A to Z)')),
                                 ])

    sender_count__gte = forms.IntegerField(label=_('Number of senders (minimum)'), required=False, min_value=1)
    sender_count__lte = forms.IntegerField(label=_('Maximum senders received from'), required=False, min_value=1)
    credit_count__gte = forms.IntegerField(label=_('Minimum credits received'), required=False, min_value=1)
    credit_count__lte = forms.IntegerField(label=_('Maximum credits received'), required=False, min_value=1)
    credit_total__gte = forms.IntegerField(label=_('Minimum total received'), required=False)
    credit_total__lte = forms.IntegerField(label=_('Maximum total received'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'),
    #                          required=False)

    prisoner_number = forms.CharField(label=_('Prisoner number'),
                                      validators=[validate_prisoner_number], required=False)
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)

    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prison_details_choices = get_prison_details_choices(self.client)
        self['prison'].field.choices = insert_blank_option(prison_details_choices['prisons'],
                                                           title=_('All prisons'))
        self['prison_region'].field.choices = insert_blank_option(prison_details_choices['regions'],
                                                                  title=_('All regions'))
        self['prison_population'].field.choices = insert_blank_option(prison_details_choices['populations'],
                                                                      title=_('All types'))
        self['prison_category'].field.choices = prison_details_choices['categories']

    def clean_credit_total__gte(self):
        credit_total__gte = self.cleaned_data.get('credit_total__gte')
        if credit_total__gte:
            return int(credit_total__gte*100)
        else:
            return credit_total__gte

    def clean_credit_total__lte(self):
        credit_total__lte = self.cleaned_data.get('credit_total__lte')
        if credit_total__lte:
            return int(credit_total__lte*100)
        else:
            return credit_total__lte

    def get_api_endpoint(self):
        return self.client.prisoners


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

    received_at__gte = forms.DateField(label=_('Received from'), help_text=_('eg 01/06/2016'), required=False)
    received_at__lt = forms.DateField(label=_('Received to'), help_text=_('eg 01/06/2016'), required=False)

    amount_pattern = forms.ChoiceField(label=_('Amount (£)'), required=False,
                                       choices=insert_blank_option(AmountPattern.get_choices(), _('Any amount')))
    amount_exact = forms.CharField(label=AmountPattern.exact.value, validators=[validate_amount], required=False)
    amount_pence = forms.IntegerField(label=AmountPattern.pence.value, min_value=0, max_value=99, required=False)

    prisoner_number = forms.CharField(
        label=_('Prisoner number'), validators=[validate_prisoner_number], required=False)
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)
    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

    sender_name = forms.CharField(label=_('Sender name'), required=False)
    sender_sort_code = forms.CharField(label=_('Sender sort code'), help_text=_('eg 01-23-45'), required=False)
    sender_account_number = forms.CharField(label=_('Sender account number'), required=False)
    sender_roll_number = forms.CharField(label=_('Sender roll number'), required=False)
    card_number_last_digits = forms.CharField(label=_('Last 4 digits of card number'), max_length=4, required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'),
    #                          required=False)

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        prison_details_choices = get_prison_details_choices(self.client)
        self['prison'].field.choices = insert_blank_option(prison_details_choices['prisons'],
                                                           title=_('All prisons'))
        self['prison_region'].field.choices = insert_blank_option(prison_details_choices['regions'],
                                                                  title=_('All regions'))
        self['prison_population'].field.choices = insert_blank_option(prison_details_choices['populations'],
                                                                      title=_('All types'))
        self['prison_category'].field.choices = prison_details_choices['categories']

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
        credits = retrieve_all_pages(
            self.client.credits.get, valid=True, reviewed=False, prison=prisons,
            received_at__lt=datetime.combine(now().date(), time(0, 0, 0, tzinfo=utc))
        )
        return credits

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
