import logging

from django.conf import settings
from django.core.urlresolvers import reverse, reverse_lazy
from django.shortcuts import redirect
from django.utils.http import is_safe_url
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from mtp_common.auth import USER_DATA_SESSION_KEY
from mtp_common.auth.api_client import get_api_session

from security import hmpps_employee_flag, not_hmpps_employee_flag
from security.forms.eligibility import HMPPSEmployeeForm

logger = logging.getLogger('mtp')


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
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial['next'] = self.request.META.get('HTTP_REFERER', '')
        return initial

    def save_user(self, flag, deactivate=False):
        request = self.request
        api_session = get_api_session(request)
        api_session.put('/users/%s/flags/%s/' % (request.user.username, flag), json={})
        if deactivate:
            api_session.delete('/users/%s/' % request.user.username)
        else:
            flags = set(request.user.user_data.get('flags') or [])
            flags.add(flag)
            flags = list(flags)
            request.user.user_data['flags'] = flags
            request.session[USER_DATA_SESSION_KEY] = request.user.user_data

    def form_valid(self, form):
        confirmation = form.cleaned_data['confirmation']
        if confirmation == 'yes':
            self.save_user(hmpps_employee_flag)
            success_url = form.cleaned_data['next']
            if success_url and is_safe_url(success_url, host=self.request.get_host()):
                self.success_url = success_url
            return super().form_valid(form)
        else:
            self.save_user(not_hmpps_employee_flag, True)
            self.request.session.flush()
            return redirect(self.not_employee_url)


class NotHMPPSEmployeeView(TemplateView):
    title = _('You can’t use this tool')
    template_name = 'not-hmpps-employee.html'

    def dispatch(self, request, *args, **kwargs):
        flags = request.user.user_data.get('flags') or []
        if request.user.is_authenticated and not_hmpps_employee_flag not in flags:
            return redirect(reverse(settings.LOGIN_REDIRECT_URL))
        return super().dispatch(request, *args, **kwargs)