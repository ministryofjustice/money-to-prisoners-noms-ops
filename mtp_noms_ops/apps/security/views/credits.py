from django.core.urlresolvers import reverse_lazy
from django.http import Http404
from django.utils.translation import gettext, gettext_lazy as _

from security.forms.credits import CreditsForm, CreditsFormV2
from security.utils import convert_date_fields
from security.templatetags.security import currency as format_currency
from security.views.base import SecurityView, SimpleSecurityDetailView


class CreditListView(SecurityView):
    """
    Legacy Credit search view

    TODO: delete after search V2 goes live.
    """
    title = _('Credits')
    form_template_name = 'security/forms/credits.html'
    template_name = 'security/credits.html'
    form_class = CreditsForm
    object_list_context_key = 'credits'


class CreditListViewV2(SecurityView):
    """
    Credit list/search view V2
    """
    title = _('Credits')
    form_class = CreditsFormV2
    template_name = 'security/credits_list.html'
    search_results_view = 'security:credit_search_results'
    simple_search_view = 'security:credit_list'
    object_list_context_key = 'credits'
    object_name = _('credit')
    object_name_plural = _('credits')


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
        credit = convert_date_fields(response['results'])[0]
        return credit

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        if self.object:
            self.title = ' '.join((format_currency(self.object['amount']) or '', gettext('credit')))
        return context_data
