from django.conf import settings
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView


class FAQView(TemplateView):
    template_name = 'faq.html'
    title = _('What do you need help with?')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['breadcrumbs_back'] = reverse_lazy('login')
        context['cashbook_url'] = settings.CASHBOOK_URL
        context['reset_password_url'] = reverse_lazy('reset_password')
        context['sign_up_url'] = reverse_lazy('sign-up')

        return context
