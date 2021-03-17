from django.conf import settings
from django.conf.urls import url
from django.urls import reverse_lazy
from django.utils.translation import gettext
from mtp_common.views import (
    GetHelpView as BaseGetHelpView,
    GetHelpSuccessView as BaseGetHelpSuccessView,
)

from .forms import ContactUsForm


class FeedbackContextMixin:
    """
    Used to override the page title using a context variable.
    """

    def get_context_data(self, **kwargs):
        kwargs['get_help_title'] = gettext('Contact us')
        return super(FeedbackContextMixin, self).get_context_data(**kwargs)


class GetHelpView(FeedbackContextMixin, BaseGetHelpView):
    form_class = ContactUsForm
    success_url = reverse_lazy('feedback_success')
    ticket_subject = 'MTP for digital team - Prisoner Money Intelligence'
    ticket_tags = ['feedback', 'mtp', 'noms-ops', settings.ENVIRONMENT]


class GetHelpSuccessView(FeedbackContextMixin, BaseGetHelpSuccessView):
    template_name = 'feedback/success.html'


urlpatterns = [
    url(r'^$', GetHelpView.as_view(), name='submit_ticket'),
    url(r'^success/$', GetHelpSuccessView.as_view(), name='feedback_success'),
]
