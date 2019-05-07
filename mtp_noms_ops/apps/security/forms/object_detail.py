from urllib.parse import urljoin

from django import forms
from django.utils.translation import gettext_lazy as _

from security.forms.object_base import SecurityDetailForm


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
    ordering = forms.ChoiceField(label=_('Order by'), required=False,
                                 initial='-created',
                                 choices=[
                                     ('created', _('Date entered (oldest to newest)')),
                                     ('-created', _('Date entered (newest to oldest)')),
                                     ('amount', _('Amount sent (low to high)')),
                                     ('-amount', _('Amount sent (high to low)')),
                                 ])

    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'Below are disbursements sent by this prisoner that {filter_description}, ' \
                                    'ordered by {ordering_description}.'
    unfiltered_description_template = 'All disbursements sent by this prisoner are shown below ordered by ' \
                                      '{ordering_description}.'

    def get_object_list_endpoint_path(self):
        return urljoin(self.get_object_endpoint_path(), 'disbursements/')
