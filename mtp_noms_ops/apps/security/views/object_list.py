from django.core.urlresolvers import reverse
from django.utils.translation import gettext_lazy as _

from security.forms.object_list import (
    SendersFormV2,
    PrisonersFormV2,
    CreditsFormV2,
    DisbursementsFormV2,
    NotificationsForm,
)
from security.views.object_base import SecurityView, ViewType


class SecuritySearchViewV2(SecurityView):
    """
    Base class for all Search Views V2.
    """

    def get_context_data(self, **kwargs):
        """
        Adds extra vars related to the search performed.
        """
        context_data = super().get_context_data(**kwargs)
        form = kwargs['form']

        is_search_results = self.view_type == ViewType.search_results

        if is_search_results and form.allow_all_prisons_simple_search():
            query_data = form.build_query_string(
                prison_selector=form.PRISON_SELECTOR_ALL_PRISONS_CHOICE_VALUE,
            )

            all_prisons_simple_search_link = f'{reverse(self.search_results_view)}?{query_data}'
        else:
            all_prisons_simple_search_link = None

        return {
            **context_data,

            'is_search_results': is_search_results,
            'is_advanced_search_results': is_search_results and form.was_advanced_search_used(),
            'is_all_prisons_simple_search_results': is_search_results and form.was_all_prisons_simple_search_used(),
            'all_prisons_simple_search_link': all_prisons_simple_search_link,
        }


class CreditListViewV2(SecuritySearchViewV2):
    """
    Credit list/search view V2
    """
    title = _('Credits')
    form_class = CreditsFormV2
    template_name = 'security/credits_list.html'
    advanced_search_template_name = 'security/credits_advanced_search.html'
    search_results_view = 'security:credit_search_results'
    simple_search_view = 'security:credit_list'
    advanced_search_view = 'security:credit_advanced_search'
    object_list_context_key = 'credits'
    object_name = _('credit')
    object_name_plural = _('credits')


class DisbursementListViewV2(SecuritySearchViewV2):
    """
    Disbursement list/search view V2
    """
    title = _('Disbursements')
    form_class = DisbursementsFormV2
    template_name = 'security/disbursements_list.html'
    advanced_search_template_name = 'security/disbursements_advanced_search.html'
    search_results_view = 'security:disbursement_search_results'
    simple_search_view = 'security:disbursement_list'
    advanced_search_view = 'security:disbursement_advanced_search'
    object_list_context_key = 'disbursements'
    object_name = _('disbursement')
    object_name_plural = _('disbursements')


class SenderListViewV2(SecuritySearchViewV2):
    """
    Sender list/search view V2.
    """
    title = _('Payment sources')
    form_class = SendersFormV2
    template_name = 'security/senders_list.html'
    advanced_search_template_name = 'security/senders_advanced_search.html'
    search_results_view = 'security:sender_search_results'
    simple_search_view = 'security:sender_list'
    advanced_search_view = 'security:sender_advanced_search'
    object_list_context_key = 'senders'
    object_name = _('payment source')
    object_name_plural = _('payment sources')

    def url_for_single_result(self, sender):
        return reverse('security:sender_detail', kwargs={'sender_id': sender['id']})


class PrisonerListViewV2(SecuritySearchViewV2):
    """
    Prisoner list/search view V2.
    """
    title = _('Prisoners')
    form_class = PrisonersFormV2
    template_name = 'security/prisoners_list.html'
    advanced_search_template_name = 'security/prisoners_advanced_search.html'
    search_results_view = 'security:prisoner_search_results'
    simple_search_view = 'security:prisoner_list'
    advanced_search_view = 'security:prisoner_advanced_search'
    object_list_context_key = 'prisoners'
    object_name = _('prisoner')
    object_name_plural = _('prisoners')

    def url_for_single_result(self, prisoner):
        return reverse('security:prisoner_detail', kwargs={'prisoner_id': prisoner['id']})


class NotificationListView(SecurityView):
    """
    Notification event view
    """
    title = _('Notifications')
    template_name = 'security/notifications.html'
    form_class = NotificationsForm
    object_list_context_key = 'date_groups'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['monitored_count'] = kwargs['form'].session.get('/monitored/').json()['count']
        return context_data
