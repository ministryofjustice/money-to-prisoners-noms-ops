from django.views.generic import TemplateView
from django.core.urlresolvers import reverse_lazy


class SecurityDashboardView(TemplateView):
    template_name = 'security/security_dashboard.html'
    success_url = reverse_lazy('security_dashboard')
