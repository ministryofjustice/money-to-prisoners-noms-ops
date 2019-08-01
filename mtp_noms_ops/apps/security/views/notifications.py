from django.conf import settings
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from security.forms.notifications import NotificationsForm
from security.views.base import SecurityView


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
