import datetime
import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.api import retrieve_all_pages_for_path
from mtp_common.auth.api_client import get_api_session

from security.forms_base import (
    SecurityForm, SecurityDetailForm,
    AmountPattern,
    parse_amount,
    validate_amount, validate_prisoner_number, validate_range_field,
    insert_blank_option, get_credit_source_choices, get_disbursement_method_choices,
)
from security.templatetags.security import currency as format_currency
from security.utils import parse_date_fields


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
    sender_postcode = forms.CharField(label=_('Sender postcode'), required=False)

    prison = forms.ChoiceField(label=_('Prison'), required=False, choices=[])
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'), required=False)

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Below are senders who {filter_description}, ordered by {ordering_description}.'
    unfiltered_description_template = 'All senders are shown below ordered by {ordering_description}. ' \
                                      'Add filters to narrow down your search.'
    description_templates = (
        ('are named ‘{sender_name}’',),
        ('have email {sender_email}',),
        ('are from postcode {sender_postcode}',),
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

    def clean_sender_postcode(self):
        sender_postcode = self.cleaned_data.get('sender_postcode')
        if sender_postcode:
            sender_postcode = re.sub(r'[\s-]+', '', sender_postcode).upper()
        return sender_postcode

    def get_object_list_endpoint_path(self):
        return '/senders/'

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
    filtered_description_template = 'Below are prisoners who {filter_description}, ordered by {ordering_description}.'
    unfiltered_description_template = 'All prisoners are shown below ordered by {ordering_description}. ' \
                                      'Add filters to narrow down your search.'
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

    def get_object_list_endpoint_path(self):
        return '/prisoners/'

    def clean_prisoner_number(self):
        prisoner_number = self.cleaned_data.get('prisoner_number')
        if prisoner_number:
            return prisoner_number.upper()
        return prisoner_number

    def get_query_data(self, allow_parameter_manipulation=True):
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            for field in ('credit_total__gte', 'credit_total__lte'):
                value = query_data.get(field)
                if value is not None:
                    query_data[field] = value * 100
        return query_data


@validate_range_field('received_at', _('Must be after the start date'), upper_limit='__lt')
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

    received_at__gte = forms.DateField(label=_('Received since'), help_text=_('for example 13/02/2018'), required=False)
    received_at__lt = forms.DateField(label=_('Received before'), help_text=_('for example 13/02/2018'), required=False)

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
    sender_postcode = forms.CharField(label=_('Sender postcode'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or sender name'), required=False)

    exclusive_date_params = ['received_at__lt']

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Below are credits sent {filter_description}, ordered by {ordering_description}.'
    unfiltered_description_template = 'All credits are shown below ordered by {ordering_description}. ' \
                                      'Add filters to narrow down your search.'
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
        ('from postcode {sender_postcode}',),
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

    def clean_amount_exact(self):
        if self.cleaned_data.get('amount_pattern') != 'exact':
            return ''
        amount = self.cleaned_data.get('amount_exact')
        if not amount:
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

    def clean_sender_postcode(self):
        sender_postcode = self.cleaned_data.get('sender_postcode')
        if sender_postcode:
            sender_postcode = re.sub(r'[\s-]+', '', sender_postcode).upper()
        return sender_postcode

    def get_object_list_endpoint_path(self):
        return '/credits/'

    def get_object_list(self):
        return parse_date_fields(super().get_object_list())

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


@validate_range_field('created', _('Must be after the start date'), upper_limit='__lt')
class DisbursementsForm(SecurityForm):
    ordering = forms.ChoiceField(label=_('Order by'), required=False,
                                 initial='-created',
                                 choices=[
                                     ('created', _('Date entered (oldest to newest)')),
                                     ('-created', _('Date entered (newest to oldest)')),
                                     ('amount', _('Amount sent (low to high)')),
                                     ('-amount', _('Amount sent (high to low)')),
                                     ('prisoner_name', _('Prisoner name (A to Z)')),
                                     ('-prisoner_name', _('Prisoner name (Z to A)')),
                                     ('prisoner_number', _('Prisoner number (A to Z)')),
                                     ('-prisoner_number', _('Prisoner number (Z to A)')),
                                 ])

    created__gte = forms.DateField(label=_('Entered since'), help_text=_('for example 13/02/2018'), required=False)
    created__lt = forms.DateField(label=_('Entered before'), help_text=_('for example 13/02/2018'), required=False)

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

    method = forms.ChoiceField(label=_('Payment method'), required=False, choices=get_disbursement_method_choices())
    recipient_name = forms.CharField(label=_('Recipient name'), required=False)
    recipient_email = forms.CharField(label=_('Recipient email'), required=False)
    city = forms.CharField(label=_('City'), required=False)
    postcode = forms.CharField(label=_('Post code'), required=False)
    sort_code = forms.CharField(label=_('Sort code'), help_text=_('for example 01-23-45'),
                                required=False)
    account_number = forms.CharField(label=_('Account number'), required=False)
    roll_number = forms.CharField(label=_('Roll number'), required=False)

    # search = forms.CharField(label=_('Prisoner name, prisoner number or recipient name'), required=False)

    exclusive_date_params = ['created__lt']

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Below are disbursements {filter_description}, ' \
                                    'ordered by {ordering_description}.'
    unfiltered_description_template = 'All disbursements are shown below ordered by {ordering_description}. ' \
                                      'Add filters to narrow down your search.'
    description_templates = (
        ('entered between {created__gte} and {created__lt}',
         'entered since {created__gte}',
         'entered before {created__lt}',),
        ('that are {amount_pattern}',),
        ('from {prisoner_name} ({prisoner_number})',
         'from prisoners named ‘{prisoner_name}’',
         'from prisoner {prisoner_number}',),
        ('{prison_preposition} {prison}',),
        ('{prison_preposition} {prison_population} {prison_category} prisons in {prison_region}',
         '{prison_preposition} {prison_category} prisons in {prison_region}',
         '{prison_preposition} {prison_population} prisons in {prison_region}',
         '{prison_preposition} {prison_population} {prison_category} prisons',
         '{prison_preposition} {prison_category} prisons',
         '{prison_preposition} {prison_population} prisons',
         '{prison_preposition} prisons in {prison_region}',),
        ('using {method} to account {account_number} {sort_code}',
         'using {method} to account {account_number}',
         'using {method} to sort code {sort_code}',
         'using {method}',),
        ('to recipients named ‘{recipient_name}’ with email {recipient_email}',
         'to recipients named {recipient_email}',
         'to recipients named ‘{recipient_name}’',),
        ('to {postcode}, {city}',
         'to {postcode} postcode',
         'to {city}',),
    )
    description_capitalisation = {
        'ordering': 'lowerfirst',
        'prison': 'preserve',
        'prison_region': 'preserve',
        'prison_category': 'lowerfirst',
    }
    default_prison_preposition = 'from'

    def clean_amount_exact(self):
        if self.cleaned_data.get('amount_pattern') != 'exact':
            return ''
        amount = self.cleaned_data.get('amount_exact')
        if not amount:
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

    def clean_sort_code(self):
        if self.cleaned_data.get('method') != 'bank_transfer':
            return ''
        sort_code = self.cleaned_data.get('sort_code')
        if sort_code:
            sort_code = sort_code.replace('-', '')
        return sort_code

    def clean_account_number(self):
        if self.cleaned_data.get('method') != 'bank_transfer':
            return ''
        return self.cleaned_data.get('account_number')

    def clean_roll_number(self):
        if self.cleaned_data.get('method') != 'bank_transfer':
            return ''
        return self.cleaned_data.get('roll_number')

    def get_object_list_endpoint_path(self):
        return '/disbursements/'

    def get_object_list(self):
        return parse_date_fields(super().get_object_list())

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
    filtered_description_template = 'Below are credits sent by this sender that {filter_description}, ' \
                                    'ordered by {ordering_description}.'
    unfiltered_description_template = 'All credits sent by this sender are shown below ordered by ' \
                                      '{ordering_description}.'

    def get_object_endpoint(self):
        return self.session.senders(self.object_id)

    def get_object_endpoint_path(self):
        return '/senders/%s/' % self.object_id


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
    filtered_description_template = 'Below are credits received by this prisoner that {filter_description}, ' \
                                    'ordered by {ordering_description}.'
    unfiltered_description_template = 'All credits received by this prisoner are shown below ordered by ' \
                                      '{ordering_description}.'

    def get_object_endpoint(self):
        return self.session.prisoners(self.object_id)

    def get_object_endpoint_path(self):
        return '/prisoners/%s/' % self.object_id


class PrisonersDisbursementDetailForm(PrisonersDetailForm):
    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Below are disbursements sent by this prisoner that {filter_description}, ' \
                                    'ordered by {ordering_description}.'
    unfiltered_description_template = 'All disbursements sent by this prisoner are shown below ordered by ' \
                                      '{ordering_description}.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prisoner_number = None

    def get_object(self):
        obj = super().get_object()
        if obj:
            self.prisoner_number = obj.get('prisoner_number')
        return obj

    def get_object_list(self):
        if not self.prisoner_number:
            return []
        return super().get_object_list()

    def get_object_list_endpoint_path(self):
        return '/disbursements/'

    def get_query_data(self, allow_parameter_manipulation=True):
        data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if not self.prisoner_number:
            self.get_object()
        data['prisoner_number'] = self.prisoner_number
        return data


class ReviewCreditsForm(GARequestErrorReportingMixin, forms.Form):
    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

        for credit in self.credits:
            self.fields['comment_%s' % credit['id']] = forms.CharField(required=False)

    @cached_property
    def session(self):
        return get_api_session(self.request)

    @cached_property
    def credits(self):
        prisons = [
            prison['nomis_id']
            for prison in self.request.user.user_data.get('prisons', [])
            if prison['pre_approval_required']
        ]
        return retrieve_all_pages_for_path(
            self.session, '/credits/', valid=True, reviewed=False, prison=prisons, resolution='pending',
            received_at__lt=datetime.datetime.combine(timezone.now().date(),
                                                      datetime.time(0, 0, 0, tzinfo=timezone.utc))
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
            self.session.post('/credits/comments/', json=comments)
        self.session.post('/credits/actions/review/', json={
            'credit_ids': list(reviewed)
        })

        return len(reviewed)
