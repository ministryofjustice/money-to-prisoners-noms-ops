from django.conf import settings
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from security.forms.object_list import (
    SendersForm,
    PrisonersForm,
    CreditsForm, DisbursementsForm,
    NotificationsForm,
)
from security.views.object_base import SecurityView


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
    Sender search view
    """
    title = _('Payment sources')
    form_template_name = 'security/forms/senders.html'
    template_name = 'security/senders.html'
    form_class = SendersForm
    object_list_context_key = 'senders'

    def url_for_single_result(self, sender):
        return reverse('security:sender_detail', kwargs={'sender_id': sender['id']})


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
