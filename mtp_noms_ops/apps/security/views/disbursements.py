from django.core.urlresolvers import reverse_lazy
from django.utils.translation import gettext, gettext_lazy as _

from security.forms.disbursements import DisbursementsForm, DisbursementsFormV2
from security.utils import convert_date_fields
from security.templatetags.security import currency as format_currency
from security.views.base import SecurityView, SimpleSecurityDetailView


class DisbursementListView(SecurityView):
    """
    Legacy Disbursement search view

    TODO: delete after search V2 goes live.
    """
    title = _('Disbursements')
    form_template_name = 'security/forms/disbursements.html'
    template_name = 'security/disbursements.html'
    form_class = DisbursementsForm
    object_list_context_key = 'disbursements'


class DisbursementListViewV2(SecurityView):
    """
    Disbursement list/search view V2
    """
    title = _('Disbursements')
    form_class = DisbursementsFormV2
    template_name = 'security/disbursements_list.html'
    search_results_view = 'security:disbursement_search_results'
    simple_search_view = 'security:disbursement_list'
    object_list_context_key = 'disbursements'
    object_name = _('disbursement')
    object_name_plural = _('disbursements')


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
