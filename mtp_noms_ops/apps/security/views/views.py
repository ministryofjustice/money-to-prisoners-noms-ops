from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView


class PolicyChangeView(TemplateView):
    title = _('Policy changes made on Nov 2nd 2020')
    template_name = 'security/policy-change-info.html'
