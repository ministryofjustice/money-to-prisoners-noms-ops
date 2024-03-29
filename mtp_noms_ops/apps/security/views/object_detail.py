from django.http import Http404
from django.urls import reverse_lazy
from django.utils.translation import gettext, gettext_lazy as _
from mtp_common.utils import format_currency

from security.forms.object_detail import (
    SendersDetailForm,
    PrisonersDetailForm, PrisonersDisbursementDetailForm,
)
from security.utils import NameSet, convert_date_fields, sender_profile_name
from security.views.object_base import SimpleSecurityDetailView, SecurityDetailView


class CreditDetailView(SimpleSecurityDetailView):
    """
    Credit detail view
    """
    title = _('Credit')
    list_title = _('Credits')
    template_name = 'security/credit.html'
    object_context_key = 'credit'
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
        credit = convert_date_fields(response['results'])[0]
        return credit

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        if self.object:
            self.title = ' '.join((format_currency(self.object['amount']) or '', gettext('credit')))
        return context_data


class DisbursementDetailView(SimpleSecurityDetailView):
    """
    Disbursement detail view
    """
    title = _('Disbursement')
    list_title = _('Disbursements')
    template_name = 'security/disbursement.html'
    object_context_key = 'disbursement'
    list_url = reverse_lazy('security:disbursement_list')

    def get_object_request_params(self):
        return {
            'url': '/disbursements/%s/' % self.kwargs['disbursement_id']
        }

    def get_object(self):
        disbursement = super().get_object()
        if disbursement:
            disbursement = convert_date_fields([disbursement])[0]
            self.format_log_set(disbursement)
            disbursement['recipient_name'] = ('%s %s' % (disbursement['recipient_first_name'],
                                                         disbursement['recipient_last_name'])).strip()
        return disbursement

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        if self.object:
            self.title = ' '.join((format_currency(self.object['amount']) or '', gettext('disbursement')))
        return context_data

    def format_log_set(self, disbursement):
        def format_staff_name(log_item):
            username = log_item['user']['username'] or _('Unknown user')
            log_item['staff_name'] = ' '.join(filter(None, (log_item['user']['first_name'],
                                                            log_item['user']['last_name']))) or username
            return log_item

        disbursement['log_set'] = sorted(
            map(format_staff_name, convert_date_fields(disbursement.get('log_set', []))),
            key=lambda log_item: log_item['created']
        )


class SenderDetailView(SecurityDetailView):
    """
    Sender profile view
    """
    title = _('Payment source')
    list_title = _('Payment sources')
    template_name = 'security/sender.html'
    form_class = SendersDetailForm
    id_kwarg_name = 'sender_id'
    object_context_key = 'sender'
    list_url = reverse_lazy('security:sender_list')

    def get_title_for_object(self, detail_object):
        return sender_profile_name(detail_object)


class PrisonerDetailView(SecurityDetailView):
    """
    Prisoner profile view showing credit list
    """
    title = _('Prisoner')
    list_title = _('Prisoners')
    template_name = 'security/prisoner.html'
    form_class = PrisonersDetailForm
    id_kwarg_name = 'prisoner_id'
    object_context_key = 'prisoner'
    list_url = reverse_lazy('security:prisoner_list')

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        prisoner = context_data.get('prisoner', {})
        if prisoner:
            context_data['provided_names'] = NameSet(
                prisoner.get('provided_names', ()), strip_titles=True
            )
        return context_data

    def get_title_for_object(self, detail_object):
        title = ' '.join(detail_object.get(key, '') for key in ('prisoner_number', 'prisoner_name'))
        return title.strip() or _('Unknown prisoner')


class PrisonerDisbursementDetailView(PrisonerDetailView):
    """
    Prisoner profile view showing disbursement list
    """
    template_name = 'security/prisoner-disbursements.html'
    form_class = PrisonersDisbursementDetailForm
    object_list_context_key = 'disbursements'
