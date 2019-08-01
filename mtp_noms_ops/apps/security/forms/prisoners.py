from urllib.parse import urljoin

from django import forms
from django.utils.translation import gettext_lazy as _

from security.forms.base import (
    SecurityDetailForm,
    SecurityForm,
    validate_prisoner_number,
    validate_range_fields,
)
from security.forms.credits import CreditsForm
from security.forms.disbursements import DisbursementsForm


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


class PrisonersFormV2(BasePrisonersForm):
    """
    Search Form for Prisoners V2.
    """
    simple_search = forms.CharField(
        label=_('Search prisoner number or name'),
        required=False,
        help_text=_('For example, name or “A1234BC”'),
    )

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Results containing {filter_description}.'
    unfiltered_description_template = ''

    description_templates = (
        ('prisoner number or name “{simple_search}”',),
    )
    description_capitalisation = {}
    unlisted_description = ''


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
    unlisted_description = CreditsForm.unlisted_description

    def get_object_endpoint(self):
        return self.session.prisoners(self.object_id)

    def get_object_endpoint_path(self):
        return '/prisoners/%s/' % self.object_id


class PrisonersDisbursementDetailForm(PrisonersDetailForm):
    ordering = forms.ChoiceField(label=_('Order by'), required=False,
                                 initial='-created',
                                 choices=[
                                     ('created', _('Date entered (oldest to newest)')),
                                     ('-created', _('Date entered (newest to oldest)')),
                                     ('amount', _('Amount sent (low to high)')),
                                     ('-amount', _('Amount sent (high to low)')),
                                 ])

    exclude_private_estate = True

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Below are disbursements sent by this prisoner that {filter_description}, ' \
                                    'ordered by {ordering_description}.'
    unfiltered_description_template = 'All disbursements sent by this prisoner are shown below ordered by ' \
                                      '{ordering_description}.'
    unlisted_description = DisbursementsForm.unlisted_description

    def get_object_list_endpoint_path(self):
        return urljoin(self.get_object_endpoint_path(), 'disbursements/')
