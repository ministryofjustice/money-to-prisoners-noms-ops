from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from mtp_common.auth.api_client import get_api_session

from security import hmpps_employee_flag, not_hmpps_employee_flag
from security.forms.eligibility import HMPPSEmployeeForm
from security.utils import save_user_flags


class HMPPSEmployeeView(FormView):
    title = _('Confirm your eligibility')
    template_name = 'hmpps-employee.html'
    form_class = HMPPSEmployeeForm
    success_url = reverse_lazy(settings.LOGIN_REDIRECT_URL)
    not_employee_url = reverse_lazy('security:not_hmpps_employee')

    def dispatch(self, request, *args, **kwargs):
        if not request.can_access_security:
            return redirect(self.success_url)
        flags = request.user.user_data.get('flags') or []
        if hmpps_employee_flag in flags:
            return redirect(self.success_url)
        if not_hmpps_employee_flag in flags:
            return redirect(self.not_employee_url)
        request.cannot_navigate_away = True
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial['next'] = self.request.META.get('HTTP_REFERER', '')
        return initial

    def form_valid(self, form):
        api_session = get_api_session(self.request)
        confirmation = form.cleaned_data['confirmation']
        if confirmation == 'yes':
            save_user_flags(self.request, hmpps_employee_flag, api_session)
            success_url = form.cleaned_data['next']
            if success_url and url_has_allowed_host_and_scheme(success_url, allowed_hosts=self.request.get_host()):
                self.success_url = success_url
            return super().form_valid(form)
        else:
            save_user_flags(self.request, not_hmpps_employee_flag, api_session)
            api_session.delete('/users/%s/' % self.request.user.username)
            self.request.session.flush()
            return redirect(self.not_employee_url)


class NotHMPPSEmployeeView(TemplateView):
    title = _('You can’t use this tool')
    template_name = 'not-hmpps-employee.html'

    def dispatch(self, request, *args, **kwargs):
        flags = request.user.user_data.get('flags') or []
        if request.user.is_authenticated and not_hmpps_employee_flag not in flags:
            return redirect(reverse(settings.LOGIN_REDIRECT_URL))
        request.cannot_navigate_away = True
        return super().dispatch(request, *args, **kwargs)
