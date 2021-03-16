from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView


class PolicyChangeView(TemplateView):
    if settings.NOVEMBER_SECOND_CHANGES_LIVE:
        title = _('What the Nov 2nd policy changes mean')
    else:
        title = _('Policy changes made on Nov 2nd 2020')

    def get_template_names(self):
        if settings.NOVEMBER_SECOND_CHANGES_LIVE:
            return ['security/policy-change-info.html']
        else:
            return ['security/policy-change-warning.html']


class FAQView(TemplateView):
    template_name = 'security/faq.html'
    title = _('What do you need help with?')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['fiu_email'] = settings.FIU_EMAIL

        return context
