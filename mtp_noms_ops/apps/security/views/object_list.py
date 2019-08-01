from django.conf import settings
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from security.forms.credits import CreditsForm, CreditsFormV2
from security.forms.disbursements import DisbursementsForm, DisbursementsFormV2
from security.forms.notifications import NotificationsForm
from security.forms.prisoners import PrisonersForm, PrisonersFormV2
from security.forms.senders import SendersForm, SendersFormV2
from security.views.object_base import SecurityView


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


class SenderListViewV2(SecurityView):
    """
    Sender list/search view V2.
    """
    title = _('Payment sources')
    form_class = SendersFormV2
    template_name = 'security/senders_list.html'
    search_results_view = 'security:sender_search_results'
    simple_search_view = 'security:sender_list'
    object_list_context_key = 'senders'
    object_name = _('payment source')
    object_name_plural = _('payment sources')

    def url_for_single_result(self, sender):
        return reverse('security:sender_detail', kwargs={'sender_id': sender['id']})


class PrisonerListView(SecurityView):
    """
    Legacy Prisoner search view

    TODO: delete after search V2 goes live.
    """
    title = _('Prisoners')
    form_template_name = 'security/forms/prisoners.html'
    template_name = 'security/prisoners.html'
    form_class = PrisonersForm
    object_list_context_key = 'prisoners'

    def url_for_single_result(self, prisoner):
        return reverse('security:prisoner_detail', kwargs={'prisoner_id': prisoner['id']})


class PrisonerListViewV2(SecurityView):
    """
    Prisoner list/search view V2.
    """
    title = _('Prisoners')
    form_class = PrisonersFormV2
    template_name = 'security/prisoners_list.html'
    search_results_view = 'security:prisoner_search_results'
    simple_search_view = 'security:prisoner_list'
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
    form_template_name = None
    template_name = 'security/notifications.html'
    form_class = NotificationsForm
    object_list_context_key = 'date_groups'

    def dispatch(self, request, *args, **kwargs):
        if not request.can_access_notifications:
            return redirect(reverse(settings.LOGIN_REDIRECT_URL))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['monitored_count'] = kwargs['form'].session.get('/monitored/').json()['count']
        return context_data
