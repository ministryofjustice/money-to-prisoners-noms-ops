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
        # TODO: Stop-gap solution: Replace with sign-up URL once functionality is there
        # context['sign_up_url'] = reverse_lazy('sign-up')
        context['sign_up_url'] = reverse_lazy('submit_ticket') + '?message=I%20want%20to%20request%20an%20account.%20%5BPlease%20provide%20your%20name%2C%20email%20address%20and%20Quantum%20ID%5D'  # noqa: E501

        return context
