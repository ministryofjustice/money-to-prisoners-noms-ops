import re

from django import forms
from django.utils.translation import gettext_lazy as _

from security.forms.base import (
    get_credit_source_choices,
    SecurityDetailForm,
    SecurityForm,
    validate_range_fields,
)


class BaseSendersForm(SecurityForm):
    """
    Senders Form Base Class.
    """
    ordering = forms.ChoiceField(
        label=_('Order by'),
        required=False,
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
        ]
    )
    prison = forms.MultipleChoiceField(label=_('Prison'), required=False, choices=[])

    def get_object_list_endpoint_path(self):
        return '/senders/'


@validate_range_fields(
    ('prisoner_count', _('Must be larger than the minimum prisoners')),
    ('credit_count', _('Must be larger than the minimum credits')),
    ('credit_total', _('Must be larger than the minimum total')),
)
class SendersForm(BaseSendersForm):
    """
    Legacy Search Form for Senders.

    TODO: delete after search V2 goes live.
    """

    prisoner_count__gte = forms.IntegerField(label=_('Number of prisoners (minimum)'), required=False, min_value=1)
    prisoner_count__lte = forms.IntegerField(label=_('Maximum prisoners sent to'), required=False, min_value=1)
    prison_count__gte = forms.IntegerField(label=_('Number of prisons (minimum)'), required=False, min_value=1)
    prison_count__lte = forms.IntegerField(label=_('Maximum prisons sent to'), required=False, min_value=1)
    credit_count__gte = forms.IntegerField(label=_('Minimum credits sent'), required=False, min_value=1)
    credit_count__lte = forms.IntegerField(label=_('Maximum credits sent'), required=False, min_value=1)
    credit_total__gte = forms.IntegerField(label=_('Minimum total sent'), required=False)
    credit_total__lte = forms.IntegerField(label=_('Maximum total sent'), required=False)

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

    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

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
    unlisted_description = 'You can’t see credits sent by post.'

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
            for field in ('credit_total__gte', 'credit_total__lte'):
                value = query_data.get(field)
                if value is not None:
                    query_data[field] = value * 100
        return query_data


class SendersFormV2(BaseSendersForm):
    """
    Search Form for Senders V2.
    """
    simple_search = forms.CharField(
        label=_('Search payment source name or email address'),
        required=False,
        help_text=_('Common or incomplete names may show many results'),
    )

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Results containing {filter_description}.'
    unfiltered_description_template = ''

    description_templates = (
        ('payment source name or email address “{simple_search}”',),
    )
    description_capitalisation = {}
    unlisted_description = ''


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
    unlisted_description = SendersForm.unlisted_description

    def get_object_endpoint(self):
        return self.session.senders(self.object_id)

    def get_object_endpoint_path(self):
        return '/senders/%s/' % self.object_id
