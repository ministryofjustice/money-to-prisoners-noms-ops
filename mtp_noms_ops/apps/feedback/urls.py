from django.conf import settings
from django.conf.urls import url
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import gettext_lazy as _
from zendesk_tickets import views
from zendesk_tickets.forms import EmailTicketForm

extra_context = {
    'breadcrumbs': [
        {'name': _('Home'), 'url': '/'},
        {'name': _('Contact us')},
    ]
}

urlpatterns = [
    url(r'^$', views.ticket,
        {
            'form_class': EmailTicketForm,
            'template_name': 'mtp_common/feedback/submit_feedback.html',
            'success_redirect_url': reverse_lazy('feedback_success'),
            'subject': 'MTP NOMS Ops Feedback',
            'tags': ['feedback', 'mtp', 'noms-ops', settings.ENVIRONMENT],
            'extra_context': extra_context,
        }, name='submit_ticket'),
    url(r'^success/$', views.success,
        {
            'template_name': 'mtp_common/feedback/success.html',
            'extra_context': extra_context,
        }, name='feedback_success'),
]
