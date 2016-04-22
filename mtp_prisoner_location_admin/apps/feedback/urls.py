from django.conf import settings
from django.conf.urls import url
from django.core.urlresolvers import reverse_lazy
from zendesk_tickets import views
from zendesk_tickets.forms import EmailTicketForm

urlpatterns = [
    url(r'^feedback/$', views.ticket,
        {
            'form_class': EmailTicketForm,
            'template_name': 'feedback/submit_feedback.html',
            'success_redirect_url': reverse_lazy('feedback_success'),
            'subject': 'MTP Prisoner Location Admin Feedback',
            'tags': ['feedback', 'mtp', 'prisoner-location-admin',
                     settings.ENVIRONMENT]
        }, name='submit_ticket'),
    url(r'^feedback/success/$', views.success,
        {
            'template_name': 'mtp_common/feedback/success.html',
        }, name='feedback_success'),
]
