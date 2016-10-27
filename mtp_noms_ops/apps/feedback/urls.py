from django.conf import settings
from django.conf.urls import url
from django.core.urlresolvers import reverse_lazy
from zendesk_tickets import views
from zendesk_tickets.forms import EmailTicketForm


urlpatterns = [
    url(r'^$', views.ticket,
        {
            'form_class': EmailTicketForm,
            'template_name': 'mtp_common/feedback/submit_feedback.html',
            'success_redirect_url': reverse_lazy('feedback_success'),
            'subject': 'MTP NOMS Ops Feedback',
            'tags': ['feedback', 'mtp', 'noms-ops', settings.ENVIRONMENT],
        }, name='submit_ticket'),
    url(r'^success/$', views.success,
        {
            'template_name': 'mtp_common/feedback/success.html',
        }, name='feedback_success'),
]
