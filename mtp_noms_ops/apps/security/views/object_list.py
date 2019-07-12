from enum import Enum

from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from security.forms.object_list import (
    SendersForm,
    SendersFormV2,
    PrisonersForm,
    CreditsForm, DisbursementsForm,
)
from security.views.object_base import SecurityView, SIMPLE_SEARCH_FORM_SUBMITTED_INPUT_NAME


class CreditListView(SecurityView):
    """
    Credit search view
    """
    title = _('Credits')
    form_template_name = 'security/forms/credits.html'
    template_name = 'security/credits.html'
    form_class = CreditsForm
    object_list_context_key = 'credits'


class DisbursementListView(SecurityView):
    """
    Disbursement search view
    """
    title = _('Disbursements')
    form_template_name = 'security/forms/disbursements.html'
    template_name = 'security/disbursements.html'
    form_class = DisbursementsForm
    object_list_context_key = 'disbursements'


class SenderListView(SecurityView):
    """
    Legacy Sender search view

    TODO: delete after search V2 goes live.
    """
    title = _('Payment sources')
    form_template_name = 'security/forms/senders.html'
    template_name = 'security/senders.html'
    form_class = SendersForm
    object_list_context_key = 'senders'

    def url_for_single_result(self, sender):
        return reverse('security:sender_detail', kwargs={'sender_id': sender['id']})


class ViewType(Enum):
    """
    Enum for the different variants of views for a specific class of objects.
    """
    simple_search_form = 'simple_search_form'
    search_results = 'search_results'


class SenderListViewV2(SecurityView):
    """
    Sender search view V2.
    """
    title = _('Payment sources')
    form_class = SendersFormV2
    view_type = ViewType.simple_search_form
    template_name = 'security/senders_list.html'
    object_list_context_key = 'senders'
    object_name = _('payment source')
    object_name_plural = _('payment sources')

    def form_valid(self, form):
        """
        If the simple form is valid and was submitted, redirect to the search results page.
        """
        if (
            self.view_type == ViewType.simple_search_form
            and SIMPLE_SEARCH_FORM_SUBMITTED_INPUT_NAME in self.request.GET
        ):
            search_results = f'{reverse("security:sender_search_results")}?{form.query_string}'
            return redirect(search_results)
        return super().form_valid(form)

    def url_for_single_result(self, sender):
        return reverse('security:sender_detail', kwargs={'sender_id': sender['id']})

    def get_context_data(self, **kwargs):
        """
        If the current view is search results, update the breadcrumbs.
        """
        context_data = super().get_context_data(**kwargs)

        if self.view_type == ViewType.search_results:
            context_data['breadcrumbs'] = [
                {'name': _('Home'), 'url': reverse('security:dashboard')},
                {'name': self.title, 'url': f'{reverse("security:sender_list")}?{kwargs["form"].query_string}'},
                {'name': _('Search results')}
            ]
            context_data['is_search_results'] = True
        return context_data


class PrisonerListView(SecurityView):
    """
    Prisoner search view
    """
    title = _('Prisoners')
    form_template_name = 'security/forms/prisoners.html'
    template_name = 'security/prisoners.html'
    form_class = PrisonersForm
    object_list_context_key = 'prisoners'

    def url_for_single_result(self, prisoner):
        return reverse('security:prisoner_detail', kwargs={'prisoner_id': prisoner['id']})
