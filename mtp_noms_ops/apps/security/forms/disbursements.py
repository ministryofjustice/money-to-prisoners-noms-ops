from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from security.forms.base import (
    AmountPattern,
    get_disbursement_method_choices,
    insert_blank_option,
    parse_amount,
    SecurityForm,
    validate_amount,
    validate_prisoner_number,
    validate_range_fields,
)
from security.templatetags.security import currency as format_currency
from security.utils import convert_date_fields


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

    amount_pattern = forms.ChoiceField(label=_('Amount (£)'), required=False,
                                       choices=insert_blank_option(AmountPattern.get_choices(), _('Any amount')))
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


class DisbursementsFormV2(BaseDisbursementsForm):
    """
    Search Form for Disbursements V2.
    """
    simple_search = forms.CharField(
        label=_('Search recipient name or prisoner number'),
        required=False,
        help_text=_('Common or incomplete names may show many results'),
    )

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Results containing {filter_description}.'
    unfiltered_description_template = ''

    description_templates = (
        ('recipient name or prisoner number “{simple_search}”',),
    )
    description_capitalisation = {}
    unlisted_description = ''
