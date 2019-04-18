from django.core.urlresolvers import reverse_lazy
from django.http import Http404
from django.utils.translation import gettext, gettext_lazy as _

from security.forms.object_detail import (
    SendersDetailForm,
    PrisonersDetailForm, PrisonersDisbursementDetailForm,
)
from security.templatetags.security import (
    currency as format_currency, credit_source as format_credit_source,
    disbursement_method as format_disbursement_method
)
from security.utils import NameSet, parse_date_fields
from security.views.object_base import SimpleSecurityDetailView, SecurityDetailView
from security.views.object_list import SenderListView, PrisonerListView


class CreditDetailView(SimpleSecurityDetailView):
    """
    Credit detail view
    """
    title = _('Credit')
    template_name = 'security/credit.html'
    object_context_key = 'credit'
    list_title = _('Credits')
    list_url = reverse_lazy('security:credit_list')

    def get_object_request_params(self):
        return {
            'url': '/credits/',
            'params': {'pk': self.kwargs['credit_id']}
        }

    def get_object(self):
        response = super().get_object()
        if not response:
            return {}
        if response['count'] != 1:
            raise Http404('credit not found')
        credit = parse_date_fields(response['results'])[0]
        return credit

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        if self.object:
            self.title = gettext('%(amount)s credit by %(payment_source)s') % {
                'amount': format_currency(self.object['amount']) or '',
                'payment_source': format_credit_source(self.object['source']).lower(),
            }
        return context_data


class DisbursementDetailView(SimpleSecurityDetailView):
    """
    Disbursement detail view
    """
    title = _('Disbursement')
    template_name = 'security/disbursement.html'
    object_context_key = 'disbursement'
    list_title = _('Disbursements')
    list_url = reverse_lazy('security:disbursement_list')

    def get_object_request_params(self):
        return {
            'url': '/disbursements/%s/' % self.kwargs['disbursement_id']
        }

    def get_object(self):
        disbursement = super().get_object()
        if disbursement:
            disbursement = parse_date_fields([disbursement])[0]
            self.format_log_set(disbursement)
            disbursement['recipient_name'] = ('%s %s' % (disbursement['recipient_first_name'],
                                                         disbursement['recipient_last_name'])).strip()
        return disbursement

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        self.title = gettext('%(amount)s disbursement by %(method)s') % {
            'amount': format_currency(self.object['amount']) or '',
            'method': format_disbursement_method(self.object['method']).lower(),
        }
        return context_data

    def format_log_set(self, disbursement):
        def format_staff_name(log_item):
            username = log_item['user']['username'] or _('Unknown user')
            log_item['staff_name'] = ' '.join(filter(None, (log_item['user']['first_name'],
                                                            log_item['user']['last_name']))) or username
            return log_item

        disbursement['log_set'] = sorted(
            map(format_staff_name, parse_date_fields(disbursement.get('log_set', []))),
            key=lambda log_item: log_item['created']
        )


class SenderDetailView(SecurityDetailView):
    """
    Sender profile view
    """
    title = _('Payment source')
    list_title = SenderListView.title
    list_url = reverse_lazy('security:sender_list')
    template_name = 'security/sender.html'
    form_class = SendersDetailForm
    id_kwarg_name = 'sender_id'
    object_context_key = 'sender'

    def get_title_for_object(self, detail_object):
        try:
            return detail_object['bank_transfer_details'][0]['sender_name']
        except (KeyError, IndexError):
            pass
        try:
            return detail_object['debit_card_details'][0]['cardholder_names'][0]
        except (KeyError, IndexError):
            pass
        return _('Unknown sender')


class PrisonerDetailView(SecurityDetailView):
    """
    Prisoner profile view showing credit list
    """
    title = _('Prisoner')
    list_title = PrisonerListView.title
    list_url = reverse_lazy('security:prisoner_list')
    template_name = 'security/prisoner.html'
    form_class = PrisonersDetailForm
    id_kwarg_name = 'prisoner_id'
    object_context_key = 'prisoner'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        prisoner = context_data.get('prisoner', {})
        if prisoner:
            context_data['provided_names'] = NameSet(
                prisoner.get('provided_names', ()), strip_titles=True
            )
        return context_data

    def get_title_for_object(self, detail_object):
        title = ' '.join(detail_object.get(key, '') for key in ('prisoner_name', 'prisoner_number'))
        return title.strip() or _('Unknown prisoner')


class PrisonerDisbursementDetailView(PrisonerDetailView):
    """
    Prisoner profile view showing disbursement list
    """
    template_name = 'security/prisoner-disbursements.html'
    form_class = PrisonersDisbursementDetailForm
    object_list_context_key = 'disbursements'
