import datetime
from math import ceil

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv4_address
from django.utils.dateparse import parse_date
from django.utils.translation import gettext_lazy as _
from mtp_common.forms.fields import SplitDateField

from security.forms.object_base import (
    AmountPattern,
    get_credit_source_choices,
    get_disbursement_method_choices,
    parse_amount,
    SecurityForm,
    validate_amount,
    validate_prisoner_number,
    validate_range_fields,
)
from security.templatetags.security import currency as format_currency
from security.utils import (
    convert_date_fields,
    remove_whitespaces_and_hyphens,
    sender_profile_name,
)

YOUR_PRISONS_QUERY_STRING_VALUE = 'mine'

END_DATE_BEFORE_START_DATE_ERROR_MSG = _('Must be after the start date.')


class SearchFormV2Mixin(forms.Form):
    """
    Mixin for SearchForm V2.
    """
    # indicates whether the form was used in advanced search
    advanced = forms.BooleanField(initial=False, required=False)

    def was_advanced_search_used(self):
        return self.cleaned_data.get('advanced', False)

    def get_api_request_params(self):
        """
        Removes `advanced` from the API call as it's not a valid filter.
        """
        api_params = super().get_api_request_params()
        api_params.pop('advanced', None)
        return api_params


class PrisonSelectorSearchFormMixin(forms.Form):
    """
    Mixin with prison fields for search V2.

    prison_selector can be one of:
    - all: all prisons
    - mine: current user's prisons
    - exact: for a specific prison

    when prison_selector == exact a `prison` value must be specified
    otherwise the form isn't valid.
    when prison_selector != exact, any `prison` value is reset as not applicable
    """
    PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE = 'exact'

    prison_selector = forms.ChoiceField(
        label=_('Choose a prison'),
        required=False,
        choices=(
            (YOUR_PRISONS_QUERY_STRING_VALUE, _('Your prisons')),
            ('all', _('All prisons')),
            (PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE, _('A specific prison')),
        ),
        initial=YOUR_PRISONS_QUERY_STRING_VALUE,
    )
    prison = forms.MultipleChoiceField(label=_('Prison name'), required=False, choices=[])

    def _update_prison_in_query_data(self, query_data):
        prison_selector = query_data.pop('prison_selector', None)
        prisons = query_data.pop('prison', [])

        if prison_selector == YOUR_PRISONS_QUERY_STRING_VALUE:
            if self.request.user_prisons:
                query_data['prison'] = [
                    prison['nomis_id']
                    for prison in self.request.user_prisons
                ]
        elif prison_selector == self.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE or not prison_selector:
            query_data['prison'] = prisons

    def get_query_data(self, allow_parameter_manipulation=True):
        """
        Updates `query_data` by translating prison_selector into the appropriate prison value for the API.
        """
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            self._update_prison_in_query_data(query_data)
        return query_data

    def _clean_prison_fields(self, cleaned_data):
        # if prison related fields are already in error don't check any further
        if set(self.errors) & {'prison_selector', 'prison'}:
            return cleaned_data

        prison_selector = cleaned_data.get('prison_selector', None)

        if prison_selector == self.PRISON_SELECTOR_EXACT_PRISON_CHOICE_VALUE:
            if not cleaned_data.get('prison'):
                self.add_error(
                    'prison',
                    ValidationError(
                        self.fields['prison'].error_messages['required'],
                        code='required',
                    ),
                )
        else:
            cleaned_data['prison'] = []

        return cleaned_data

    def clean(self):
        """
        Validates the prison related fields and resets the prison field
        if incompatible with the choosen prison_selector.
        """
        cleaned_data = super().clean()
        return self._clean_prison_fields(cleaned_data)


class AmountSearchFormMixin(forms.Form):
    """
    Mixin for the amount fields and related logic.
    """
    amount_pattern = forms.ChoiceField(
        label=_('Amount'),
        required=False,
        choices=AmountPattern.get_choices(),
    )
    amount_exact = forms.CharField(
        label=AmountPattern.exact.value,
        validators=[validate_amount],
        required=False,
    )
    amount_pence = forms.IntegerField(
        label=AmountPattern.pence.value,
        min_value=0,
        max_value=99,
        required=False,
    )

    def _update_amounts_in_query_data(self, query_data):
        amount_pattern = query_data.pop('amount_pattern', None)
        try:
            amount_pattern = AmountPattern[amount_pattern]
        except KeyError:
            return

        amount_exact = query_data.pop('amount_exact', None)
        amount_pence = query_data.pop('amount_pence', None)

        if amount_pattern == AmountPattern.not_integral:
            query_data['exclude_amount__endswith'] = '00'
        elif amount_pattern == AmountPattern.not_multiple_5:
            query_data['exclude_amount__regex'] = '(500|000)$'
        elif amount_pattern == AmountPattern.not_multiple_10:
            query_data['exclude_amount__endswith'] = '000'
        elif amount_pattern == AmountPattern.gte_100:
            query_data['amount__gte'] = '10000'
        elif amount_pattern == AmountPattern.exact:
            query_data['amount'] = parse_amount(amount_exact or '', as_int=False)
        elif amount_pattern == AmountPattern.pence:
            query_data['amount__endswith'] = '' if amount_pence is None else '%02d' % amount_pence
        else:
            raise NotImplementedError

    def get_query_data(self, allow_parameter_manipulation=True):
        """
        Updates `query_data` by translating amount_pattern, amount_exact and amount_pence
        into appropriate filters for the API.
        """
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            self._update_amounts_in_query_data(query_data)
        return query_data

    def _clean_amount_fields(self, cleaned_data):
        # if amount fields are already in error dont' check any further
        if set(self.errors) & {'amount_pattern', 'amount_exact', 'amount_pence'}:
            return cleaned_data

        try:
            amount_pattern = AmountPattern[cleaned_data.get('amount_pattern')]
        except KeyError:
            amount_pattern = None

        if amount_pattern == AmountPattern.exact:
            if not cleaned_data.get('amount_exact'):
                self.add_error(
                    'amount_exact',
                    ValidationError(_('This field is required for the selected amount pattern.'), code='required'),
                )
        else:
            cleaned_data['amount_exact'] = ''

        if amount_pattern == AmountPattern.pence:
            if cleaned_data.get('amount_pence') is None:
                self.add_error(
                    'amount_pence',
                    ValidationError(_('This field is required for the selected amount pattern.'), code='required'),
                )
        else:
            cleaned_data['amount_pence'] = ''
        return cleaned_data

    def clean(self):
        """
        Validates the amount fields and resets amount_exact, amount_pence if incompatible with
        the choosen amount_pattern.
        """
        cleaned_data = super().clean()
        return self._clean_amount_fields(cleaned_data)


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
        return remove_whitespaces_and_hyphens(self.cleaned_data.get('sender_sort_code'))

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
        return remove_whitespaces_and_hyphens(self.cleaned_data.get('sender_postcode'))

    def get_query_data(self, allow_parameter_manipulation=True):
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            for field in ('credit_total__gte', 'credit_total__lte'):
                value = query_data.get(field)
                if value is not None:
                    query_data[field] = value * 100
        return query_data


class SendersFormV2(SearchFormV2Mixin, BaseSendersForm):
    """
    Search Form for Senders V2.
    """
    simple_search = forms.CharField(
        label=_('Search payment source name or email address'),
        required=False,
        help_text=_('Common or incomplete names may show many results'),
    )
    sender_name = forms.CharField(label=_('Name'), required=False)
    sender_email = forms.CharField(label=_('Email'), required=False)
    sender_postcode = forms.CharField(label=_('Postcode'), required=False)
    card_number_last_digits = forms.CharField(label=_('Last 4 digits of card number'), max_length=4, required=False)
    sender_account_number = forms.CharField(label=_('Account number'), required=False)
    sender_sort_code = forms.CharField(label=_('Sort code'), required=False)

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Results containing {filter_description}.'
    unfiltered_description_template = ''

    description_templates = (
        ('payment source name or email address “{simple_search}”',),
    )
    description_capitalisation = {}
    unlisted_description = ''

    def clean_sender_postcode(self):
        sender_postcode = self.cleaned_data.get('sender_postcode')
        return remove_whitespaces_and_hyphens(sender_postcode)

    def clean_sender_sort_code(self):
        sender_sort_code = self.cleaned_data.get('sender_sort_code')
        return remove_whitespaces_and_hyphens(sender_sort_code)


class BasePrisonersForm(SecurityForm):
    """
    Prisoners Form Base Class.
    """
    ordering = forms.ChoiceField(
        label=_('Order by'),
        required=False,
        initial='-sender_count',
        choices=[
            ('sender_count', _('Number of senders (low to high)')),
            ('-sender_count', _('Number of senders (high to low)')),
            ('credit_count', _('Number of credits (low to high)')),
            ('-credit_count', _('Number of credits (high to low)')),
            ('credit_total', _('Total received (low to high)')),
            ('-credit_total', _('Total received (high to low)')),
            ('recipient_count', _('Number of recipients (low to high)')),
            ('-recipient_count', _('Number of recipients (high to low)')),
            ('disbursement_count', _('Number of disbursements (low to high)')),
            ('-disbursement_count', _('Number of disbursements (high to low)')),
            ('disbursement_total', _('Total sent (low to high)')),
            ('-disbursement_total', _('Total sent (high to low)')),
            ('prisoner_name', _('Prisoner name (A to Z)')),
            ('-prisoner_name', _('Prisoner name (Z to A)')),
            ('prisoner_number', _('Prisoner number (A to Z)')),
            ('-prisoner_number', _('Prisoner number (Z to A)')),
        ],
    )
    prison = forms.MultipleChoiceField(label=_('Prison'), required=False, choices=[])

    def get_object_list_endpoint_path(self):
        return '/prisoners/'


@validate_range_fields(
    ('sender_count', _('Must be larger than the minimum senders')),
    ('credit_count', _('Must be larger than the minimum credits')),
    ('credit_total', _('Must be larger than the minimum total received')),
    ('recipient_count', _('Must be larger than the minimum recipients')),
    ('disbursement_count', _('Must be larger than the minimum disbursements')),
    ('disbursement_total', _('Must be larger than the minimum total sent')),
)
class PrisonersForm(BasePrisonersForm):
    """
    Legacy Search Form for Prisoners.

    TODO: delete after search V2 goes live.
    """

    sender_count__gte = forms.IntegerField(label=_('Number of senders (minimum)'), required=False, min_value=1)
    sender_count__lte = forms.IntegerField(label=_('Maximum senders received from'), required=False, min_value=1)
    credit_count__gte = forms.IntegerField(label=_('Minimum credits received'), required=False, min_value=1)
    credit_count__lte = forms.IntegerField(label=_('Maximum credits received'), required=False, min_value=1)
    credit_total__gte = forms.IntegerField(label=_('Minimum total received'), required=False)
    credit_total__lte = forms.IntegerField(label=_('Maximum total received'), required=False)

    recipient_count__gte = forms.IntegerField(label=_('Number of recipients (minimum)'), required=False, min_value=1)
    recipient_count__lte = forms.IntegerField(label=_('Maximum recipients sent to'), required=False, min_value=1)
    disbursement_count__gte = forms.IntegerField(label=_('Minimum disbursements sent'), required=False, min_value=1)
    disbursement_count__lte = forms.IntegerField(label=_('Maximum disbursements sent'), required=False, min_value=1)
    disbursement_total__gte = forms.IntegerField(label=_('Minimum total sent'), required=False)
    disbursement_total__lte = forms.IntegerField(label=_('Maximum total sent'), required=False)

    prisoner_number = forms.CharField(label=_('Prisoner number'),
                                      validators=[validate_prisoner_number], required=False)
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

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
        ('sent to {recipient_count__gte}-{recipient_count__lte} senders',
         'sent to at least {recipient_count__gte} senders',
         'sent to at most {recipient_count__lte} senders',),
        ('sent between {disbursement_count__gte}-{disbursement_count__lte} credits',
         'sent at least {disbursement_count__gte} credits',
         'sent at most {disbursement_count__lte} credits',),
        ('sent between £{disbursement_total__gte}-{disbursement_total__lte}',
         'sent at least £{disbursement_total__gte}',
         'sent at most £{disbursement_total__lte}',),
    )
    description_capitalisation = {
        'ordering': 'lowerfirst',
        'prison': 'preserve',
        'prison_region': 'preserve',
        'prison_category': 'lowerfirst',
    }
    unlisted_description = 'You can only see prisoners who received or sent money.'

    def clean_prisoner_number(self):
        prisoner_number = self.cleaned_data.get('prisoner_number')
        if prisoner_number:
            return prisoner_number.upper()
        return prisoner_number

    def get_query_data(self, allow_parameter_manipulation=True):
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            fields = (
                'credit_total__gte', 'credit_total__lte',
                'disbursement_total__gte', 'disbursement_total__lte',
            )
            for field in fields:
                value = query_data.get(field)
                if value is not None:
                    query_data[field] = value * 100
        return query_data


class PrisonersFormV2(SearchFormV2Mixin, BasePrisonersForm):
    """
    Search Form for Prisoners V2.
    """
    simple_search = forms.CharField(
        label=_('Search prisoner number or name'),
        required=False,
        help_text=_('For example, name or “A1234BC”'),
    )
    prisoner_number = forms.CharField(
        label=_('Prisoner number'),
        validators=[validate_prisoner_number],
        required=False,
    )
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Results containing {filter_description}.'
    unfiltered_description_template = ''

    description_templates = (
        ('prisoner number or name “{simple_search}”',),
    )
    description_capitalisation = {}
    unlisted_description = ''

    def clean_prisoner_number(self):
        """
        Make sure prisoner number is always uppercase.
        """
        prisoner_number = self.cleaned_data.get('prisoner_number')
        if not prisoner_number:
            return prisoner_number

        return prisoner_number.upper()


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

    amount_pattern = forms.ChoiceField(
        label=_('Amount (£)'),
        required=False,
        choices=AmountPattern.get_choices(),
    )
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
        return remove_whitespaces_and_hyphens(self.cleaned_data.get('sender_sort_code'))

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
        return remove_whitespaces_and_hyphens(self.cleaned_data.get('sender_postcode'))

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


class CreditsFormV2(SearchFormV2Mixin, AmountSearchFormMixin, BaseCreditsForm):
    """
    Search Form for Credits V2.
    """
    simple_search = forms.CharField(
        label=_('Search payment source name, email address or prisoner number'),
        required=False,
        help_text=_('Common or incomplete names may show many results'),
    )
    received_at__gte = SplitDateField(
        label=_('From'),
        required=False,
        help_text=_('For example, 01 08 2007'),
    )
    received_at__lt = SplitDateField(
        label=_('To'),
        required=False,
        help_text=_('For example, 01 08 2007'),
    )

    sender_name = forms.CharField(label=_('Name'), required=False)
    sender_email = forms.CharField(label=_('Email'), required=False)
    sender_postcode = forms.CharField(label=_('Postcode'), required=False)
    sender_ip_address = forms.CharField(
        label=_('IP Address'),
        validators=[validate_ipv4_address],
        required=False,
    )
    card_number_last_digits = forms.CharField(label=_('Last 4 digits of card number'), max_length=4, required=False)
    sender_account_number = forms.CharField(label=_('Account number'), required=False)
    sender_sort_code = forms.CharField(label=_('Sort code'), required=False)

    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)
    prisoner_number = forms.CharField(
        label=_('Prisoner number'),
        validators=[validate_prisoner_number],
        required=False,
    )

    exclusive_date_params = ['received_at__lt']

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Results containing {filter_description}.'
    unfiltered_description_template = ''

    description_templates = (
        ('payment source name, email address or prisoner number “{simple_search}”',),
    )
    description_capitalisation = {}
    unlisted_description = ''

    def clean_sender_postcode(self):
        sender_postcode = self.cleaned_data.get('sender_postcode')
        return remove_whitespaces_and_hyphens(sender_postcode)

    def clean_sender_sort_code(self):
        sender_sort_code = self.cleaned_data.get('sender_sort_code')
        return remove_whitespaces_and_hyphens(sender_sort_code)

    def clean_prisoner_number(self):
        """
        Make sure prisoner number is always uppercase.
        """
        prisoner_number = self.cleaned_data.get('prisoner_number')
        if not prisoner_number:
            return prisoner_number

        return prisoner_number.upper()

    def get_query_data(self, allow_parameter_manipulation=True):
        """
        Split Date Fields are compressed into a datetime.date values.
        This is okay for API calls but when we need to preserve the query string
        (e.g. redirect to search results page or export), we need to keep the split
        values instead.
        """
        query_data = super().get_query_data(
            allow_parameter_manipulation=allow_parameter_manipulation,
        )

        if not allow_parameter_manipulation:
            for date_field_name in ('received_at__gte', 'received_at__lt'):
                value = query_data.pop(date_field_name, None)
                if not value:
                    continue

                query_data.update(
                    {
                        f'{date_field_name}_{index}': value_part
                        for index, value_part in enumerate(
                            SplitDateField().widget.decompress(value),
                        )
                    },
                )
        return query_data

    def _clean_dates(self, cleaned_data):
        received_at__gte = cleaned_data.get('received_at__gte')
        received_at__lt = cleaned_data.get('received_at__lt')

        if received_at__gte and received_at__lt and received_at__gte > received_at__lt:
            self.add_error(
                'received_at__lt',
                ValidationError(END_DATE_BEFORE_START_DATE_ERROR_MSG, code='bound_ordering'),
            )
        return cleaned_data

    def clean(self):
        """
        Validates dates.
        """
        cleaned_data = super().clean()
        return self._clean_dates(cleaned_data)


class BaseDisbursementsForm(SecurityForm):
    """
    Disbursements Form Base Class.
    """
    ordering = forms.ChoiceField(
        label=_('Order by'),
        required=False,
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
        ],
    )

    prison = forms.MultipleChoiceField(label=_('Prison'), required=False, choices=[])

    exclude_private_estate = True

    def get_object_list(self):
        object_list = super().get_object_list()
        convert_date_fields(object_list)
        return object_list

    def get_object_list_endpoint_path(self):
        return '/disbursements/'


@validate_range_fields(
    ('created', _('Must be after the start date'), '__lt'),
)
class DisbursementsForm(BaseDisbursementsForm):
    """
    Legacy Search Form for Disbursements.

    TODO: delete after search V2 goes live.
    """
    created__gte = forms.DateField(label=_('Entered since'), help_text=_('For example, 13/02/2018'), required=False)
    created__lt = forms.DateField(label=_('Entered before'), help_text=_('For example, 13/02/2018'), required=False)

    amount_pattern = forms.ChoiceField(
        label=_('Amount (£)'),
        required=False,
        choices=AmountPattern.get_choices(),
    )
    amount_exact = forms.CharField(label=AmountPattern.exact.value, validators=[validate_amount], required=False)
    amount_pence = forms.IntegerField(label=AmountPattern.pence.value, min_value=0, max_value=99, required=False)

    prisoner_number = forms.CharField(label=_('Prisoner number'), validators=[validate_prisoner_number], required=False)
    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)
    prison_region = forms.ChoiceField(label=_('Prison region'), required=False, choices=[])
    prison_population = forms.ChoiceField(label=_('Prison type'), required=False, choices=[])
    prison_category = forms.ChoiceField(label=_('Prison category'), required=False, choices=[])

    method = forms.ChoiceField(label=_('Payment method'), required=False, choices=get_disbursement_method_choices(),
                               help_text=_('Select to see filters like account number'))
    recipient_name = forms.CharField(label=_('Recipient name'), required=False)
    recipient_email = forms.CharField(label=_('Recipient email'), required=False)
    city = forms.CharField(label=_('City'), required=False)
    postcode = forms.CharField(label=_('Postcode'), required=False)
    sort_code = forms.CharField(label=_('Sort code'), help_text=_('For example, 01-23-45'),
                                required=False)
    account_number = forms.CharField(label=_('Account number'), required=False)
    roll_number = forms.CharField(label=_('Roll number'), required=False)
    invoice_number = forms.CharField(label=_('Invoice number'), required=False)

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
    unlisted_description = 'You can’t see cash or postal orders here.'

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
        return remove_whitespaces_and_hyphens(self.cleaned_data.get('sort_code'))

    def clean_account_number(self):
        if self.cleaned_data.get('method') != 'bank_transfer':
            return ''
        return self.cleaned_data.get('account_number')

    def clean_roll_number(self):
        if self.cleaned_data.get('method') != 'bank_transfer':
            return ''
        return self.cleaned_data.get('roll_number')

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


class DisbursementsFormV2(SearchFormV2Mixin, AmountSearchFormMixin, BaseDisbursementsForm):
    """
    Search Form for Disbursements V2.
    """
    simple_search = forms.CharField(
        label=_('Search recipient name or prisoner number'),
        required=False,
        help_text=_('Common or incomplete names may show many results'),
    )
    created__gte = SplitDateField(
        label=_('From'),
        required=False,
        help_text=_('For example, 01 08 2007'),
    )
    created__lt = SplitDateField(
        label=_('To'),
        required=False,
        help_text=_('For example, 01 08 2007'),
    )

    recipient_name = forms.CharField(label=_('Name'), required=False)
    recipient_email = forms.CharField(label=_('Email'), required=False)
    postcode = forms.CharField(label=_('Postcode'), required=False)
    account_number = forms.CharField(label=_('Account number'), required=False)
    sort_code = forms.CharField(label=_('Sort code'), required=False)

    prisoner_name = forms.CharField(label=_('Prisoner name'), required=False)
    prisoner_number = forms.CharField(
        label=_('Prisoner number'),
        validators=[validate_prisoner_number],
        required=False,
    )

    invoice_number = forms.CharField(label=_('Invoice number'), required=False)

    exclusive_date_params = ['created__lt']

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Results containing {filter_description}.'
    unfiltered_description_template = ''

    description_templates = (
        ('recipient name or prisoner number “{simple_search}”',),
    )
    description_capitalisation = {}
    unlisted_description = ''

    def clean_postcode(self):
        postcode = self.cleaned_data.get('postcode')
        return remove_whitespaces_and_hyphens(postcode)

    def clean_sort_code(self):
        sort_code = self.cleaned_data.get('sort_code')
        return remove_whitespaces_and_hyphens(sort_code)

    def clean_prisoner_number(self):
        """
        Make sure prisoner number is always uppercase.
        """
        prisoner_number = self.cleaned_data.get('prisoner_number')
        if not prisoner_number:
            return prisoner_number

        return prisoner_number.upper()

    def get_query_data(self, allow_parameter_manipulation=True):
        """
        Split Date Fields are compressed into a datetime.date values.
        This is okay for API calls but when we need to preserve the query string
        (e.g. redirect to search results page or export), we need to keep the split
        values instead.
        """
        query_data = super().get_query_data(
            allow_parameter_manipulation=allow_parameter_manipulation,
        )

        if not allow_parameter_manipulation:
            for date_field_name in ('created__gte', 'created__lt'):
                value = query_data.pop(date_field_name, None)
                if not value:
                    continue

                query_data.update(
                    {
                        f'{date_field_name}_{index}': value_part
                        for index, value_part in enumerate(
                            SplitDateField().widget.decompress(value),
                        )
                    },
                )
        return query_data

    def _clean_dates(self, cleaned_data):
        created__gte = cleaned_data.get('created__gte')
        created__lt = cleaned_data.get('created__lt')

        if created__gte and created__lt and created__gte > created__lt:
            self.add_error(
                'created__lt',
                ValidationError(END_DATE_BEFORE_START_DATE_ERROR_MSG, code='bound_ordering'),
            )
        return cleaned_data

    def clean(self):
        """
        Validates dates.
        """
        cleaned_data = super().clean()
        return self._clean_dates(cleaned_data)


@validate_range_fields(
    ('triggered_at', _('Must be after the start date'), '__lt'),
)
class NotificationsForm(SecurityForm):
    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'All notifications are shown below.'
    unfiltered_description_template = 'All notifications are shown below.'
    description_templates = ()

    page_size = 25

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        self.date_count = 0

    def get_object_list_endpoint_path(self):
        return '/events/'

    def get_query_data(self, allow_parameter_manipulation=True):
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            query_data['rule'] = ('MONP', 'MONS')
        return query_data

    def get_api_request_page_params(self):
        filters = super().get_api_request_page_params()
        if filters is not None:
            data = self.session.get('/events/pages/', params=filters).json()
            self.date_count = data['count']
            filters['ordering'] = '-triggered_at'
            del filters['offset']
            del filters['limit']
            if data['newest']:
                filters['triggered_at__lt'] = parse_date(data['newest']) + datetime.timedelta(days=1)
                filters['triggered_at__gte'] = parse_date(data['oldest'])
        return filters

    def get_object_list(self):
        events = convert_date_fields(super().get_object_list())
        date_groups = map(summarise_date_group, group_events_by_date(events))

        self.page_count = int(ceil(self.date_count / self.page_size))
        self.total_count = self.date_count
        return date_groups


def make_date_group(date):
    return {
        'date': date,
        'senders': {},
        'prisoners': {},
    }


def make_date_group_profile(profile_id, description):
    return {
        'id': profile_id,
        'description': description,
        'credit_ids': set(),
        'disbursement_ids': set(),
    }


def group_events_by_date(events):
    date_groups = []
    date_group = make_date_group(None)
    for event in events:
        event_date = event['triggered_at'].date()
        if event_date != date_group['date']:
            date_group = make_date_group(event_date)
            date_groups.append(date_group)

        if event['sender_profile']:
            profile = event['sender_profile']
            if profile['id'] in date_group['senders']:
                details = date_group['senders'][profile['id']]
            else:
                details = make_date_group_profile(
                    profile['id'],
                    sender_profile_name(profile)
                )
                date_group['senders'][profile['id']] = details
            if event['credit_id']:
                details['credit_ids'].add(event['credit_id'])
            if event['disbursement_id']:
                details['disbursement_ids'].add(event['disbursement_id'])

        if event['prisoner_profile']:
            profile = event['prisoner_profile']
            if profile['id'] in date_group['prisoners']:
                details = date_group['prisoners'][profile['id']]
            else:
                details = make_date_group_profile(
                    profile['id'],
                    f"{profile['prisoner_name']} ({profile['prisoner_number']})"
                )
                date_group['prisoners'][profile['id']] = details
            if event['credit_id']:
                details['credit_ids'].add(event['credit_id'])
            if event['disbursement_id']:
                details['disbursement_ids'].add(event['disbursement_id'])
    return date_groups


def summarise_date_group(date_group):
    date_group_transaction_count = 0

    sender_summaries = []
    senders = sorted(
        date_group['senders'].values(),
        key=lambda s: s['description']
    )
    for sender in senders:
        profile_transaction_count = len(sender['credit_ids'])
        date_group_transaction_count += profile_transaction_count
        sender_summaries.append({
            'id': sender['id'],
            'transaction_count': profile_transaction_count,
            'description': sender['description'],
        })

    prisoner_summaries = []
    prisoners = sorted(
        date_group['prisoners'].values(),
        key=lambda p: p['description']
    )
    for prisoner in prisoners:
        disbursements_only = bool(prisoner['disbursement_ids'] and not prisoner['credit_ids'])
        profile_transaction_count = len(prisoner['credit_ids']) + len(prisoner['disbursement_ids'])
        date_group_transaction_count += profile_transaction_count
        prisoner_summaries.append({
            'id': prisoner['id'],
            'transaction_count': profile_transaction_count,
            'description': prisoner['description'],
            'disbursements_only': disbursements_only,
        })

    return {
        'date': date_group['date'],
        'transaction_count': date_group_transaction_count,
        'senders': sender_summaries,
        'prisoners': prisoner_summaries,
    }
