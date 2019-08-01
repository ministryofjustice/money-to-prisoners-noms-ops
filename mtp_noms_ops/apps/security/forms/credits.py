import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv4_address
from django.utils.translation import gettext_lazy as _

from security.forms.base import (
    AmountPattern,
    get_credit_source_choices,
    insert_blank_option,
    parse_amount,
    SecurityForm,
    validate_amount,
    validate_prisoner_number,
    validate_range_fields,
)
from security.templatetags.security import currency as format_currency
from security.utils import convert_date_fields


class BaseCreditsForm(SecurityForm):
    """
    Credits Form Base Class.
    """
    ordering = forms.ChoiceField(
        label=_('Order by'),
        required=False,
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
        ],
    )
    prison = forms.MultipleChoiceField(label=_('Prison'), required=False, choices=[])

    def get_object_list(self):
        object_list = super().get_object_list()
        convert_date_fields(object_list)
        return object_list

    def get_object_list_endpoint_path(self):
        return '/credits/'


@validate_range_fields(
    ('received_at', _('Must be after the start date'), '__lt'),
)
class CreditsForm(BaseCreditsForm):
    """
    Legacy Search Form for Credits.

    TODO: delete after search V2 goes live.
    """

    received_at__gte = forms.DateField(label=_('Received since'), required=False,
                                       help_text=_('For example, 13/02/2018'))
    received_at__lt = forms.DateField(label=_('Received before'), required=False,
                                      help_text=_('For example, 13/02/2018'))

    amount_pattern = forms.ChoiceField(label=_('Amount (£)'), required=False,
                                       choices=insert_blank_option(AmountPattern.get_choices(), _('Any amount')))
    amount_exact = forms.CharField(label=AmountPattern.exact.value, validators=[validate_amount], required=False)
    amount_pence = forms.IntegerField(label=AmountPattern.pence.value, min_value=0, max_value=99, required=False)

    prisoner_number = forms.CharField(label=_('Prisoner number'), validators=[validate_prisoner_number], required=False)
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

    sender_name = forms.CharField(label=_('Sender name'), required=False)
    source = forms.ChoiceField(label=_('Payment method'), required=False, choices=get_credit_source_choices(),
                               help_text=_('Select to see filters like card number or postcode'))
    sender_sort_code = forms.CharField(label=_('Sender sort code'), required=False,
                                       help_text=_('For example, 01-23-45'))
    sender_account_number = forms.CharField(label=_('Sender account number'), required=False)
    sender_roll_number = forms.CharField(label=_('Sender roll number'), required=False)
    card_number_last_digits = forms.CharField(label=_('Last 4 digits of card number'), max_length=4, required=False)
    sender_email = forms.CharField(label=_('Sender email'), required=False)
    sender_postcode = forms.CharField(label=_('Sender postcode'), required=False)
    sender_ip_address = forms.CharField(label=_('Sender IP address'),
                                        validators=[validate_ipv4_address], required=False)

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
        ('from IP {sender_ip_address}',),
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
    unlisted_description = 'You can’t see credits received by post.'

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


class CreditsFormV2(BaseCreditsForm):
    """
    Search Form for Credits V2.
    """
    simple_search = forms.CharField(
        label=_('Search payment source name, email address or prisoner number'),
        required=False,
        help_text=_('Common or incomplete names may show many results'),
    )

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Results containing {filter_description}.'
    unfiltered_description_template = ''

    description_templates = (
        ('payment source name, email address or prisoner number “{simple_search}”',),
    )
    description_capitalisation = {}
    unlisted_description = ''
