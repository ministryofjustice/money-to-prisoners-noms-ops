from urllib.parse import urlencode

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import SuccessURLAllowedHostsMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import is_safe_url
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from mtp_common.auth.api_client import get_api_session

from security import confirmed_prisons_flag, provided_job_info_flag
from settings.forms import ConfirmPrisonForm, ChangePrisonForm, ALL_PRISONS_CODE, JobInformationForm
from security.models import EmailNotifications
from security.utils import save_user_flags, can_skip_confirming_prisons, has_provided_job_information


class NomsOpsSettingsView(TemplateView):
    title = _('Settings')
    template_name = 'settings/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = get_api_session(self.request)
        email_preferences = session.get('/emailpreferences/').json()
        context['email_notifications'] = email_preferences['frequency'] != EmailNotifications.never
        return context

    def post(self, *args, **kwargs):
        if 'email_notifications' in self.request.POST:
            session = get_api_session(self.request)
            if self.request.POST['email_notifications'] == 'True':
                session.post('/emailpreferences/', json={'frequency': EmailNotifications.daily})
            else:
                session.post('/emailpreferences/', json={'frequency': EmailNotifications.never})
        return redirect(reverse_lazy('settings'))


class ConfirmPrisonsView(FormView):
    title = _('Confirm your prisons')
    template_name = 'settings/confirm-prisons.html'
    form_class = ConfirmPrisonForm
    success_url = reverse_lazy('confirm_prisons_confirmation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_prisons'] = ','.join([
            p['nomis_id'] for p in self.request.user.user_data['prisons']
        ] if self.request.user.user_data.get('prisons') else ['ALL'])

        selected_prisons = self.request.GET.getlist('prisons')
        if not selected_prisons:
            selected_prisons = [
                p['nomis_id'] for p in self.request.user.user_data['prisons']
            ]
            if not selected_prisons:
                selected_prisons = [ALL_PRISONS_CODE]
        query_dict = self.request.GET.copy()
        query_dict['prisons'] = selected_prisons
        context['change_prison_query'] = urlencode(query_dict, doseq=True)
        self.request.cannot_navigate_away = not can_skip_confirming_prisons(self.request.user)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.save()
        save_user_flags(self.request, confirmed_prisons_flag)
        return redirect(self.get_success_url())

    def get_success_url(self):
        if 'next' in self.request.GET:
            return '{path}?{query}'.format(
                path=self.success_url,
                query=urlencode({'next': self.request.GET['next']})
            )
        return self.success_url


class ChangePrisonsView(SuccessURLAllowedHostsMixin, FormView):
    title = _('Change prisons')
    template_name = 'settings/confirm-prisons-change.html'
    form_class = ChangePrisonForm

    def get_success_url(self):
        """
        Returns the REDIRECT_FIELD_NAME value in GET if it exists and it's valid
        or the url to the settings page otherwise.
        """
        if REDIRECT_FIELD_NAME in self.request.GET:
            next_page = self.request.GET[REDIRECT_FIELD_NAME]
            url_is_safe = is_safe_url(
                url=next_page,
                allowed_hosts=self.get_success_url_allowed_hosts(),
                require_https=self.request.is_secure(),
            )

            if url_is_safe:
                return next_page
        return reverse('settings')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['data_attrs'] = {
            'data-autocomplete-error-empty': _('Type a prison name'),
            'data-autocomplete-error-summary': _('There was a problem'),
            'data-event-category': 'PrisonConfirmation',
        }
        context['current_prisons'] = ','.join([
            p['nomis_id'] for p in self.request.user.user_data['prisons']
        ] if self.request.user.user_data.get('prisons') else ['ALL'])
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.save()
        save_user_flags(self.request, confirmed_prisons_flag)
        return redirect(self.get_success_url())


class AddOrRemovePrisonsView(ChangePrisonsView):
    title = _('Add or remove prisons')
    template_name = 'settings/confirm-prisons-change.html'
    form_class = ChangePrisonForm
    success_url = reverse_lazy('confirm_prisons')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.request.cannot_navigate_away = not can_skip_confirming_prisons(self.request.user)
        return context

    def form_valid(self, form):
        return redirect('{path}?{query}'.format(
            path=self.get_success_url(),
            query=form.get_confirmation_query_string()
        ))


class ConfirmPrisonsConfirmationView(TemplateView):
    title = _('Your prisons have been saved')
    template_name = 'settings/confirm-prisons-confirmation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['prisons'] = self.request.user_prisons
        return context


class JobInformationView(SuccessURLAllowedHostsMixin, FormView):
    title = _('Help us improve this service')
    template_name = 'settings/job-information.html'
    form_class = JobInformationForm

    def dispatch(self, request, *args, **kwargs):
        request.cannot_navigate_away = True
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if REDIRECT_FIELD_NAME in self.request.GET:
            next_page = self.request.GET[REDIRECT_FIELD_NAME]
            url_is_safe = is_safe_url(
                url=next_page,
                allowed_hosts=self.get_success_url_allowed_hosts(),
                require_https=self.request.is_secure(),
            )

            if url_is_safe:
                return next_page
        return reverse('security:dashboard')

    def form_valid(self, form):
        if has_provided_job_information(self.request.user):
            return redirect(self.get_success_url())

        session = get_api_session(self.request)
        session.post('/job-information/', json={'title': form.cleaned_data['job_title_or_other'],
                                                'prison_estate': form.cleaned_data['prison_estate'],
                                                'tasks': form.cleaned_data['tasks']})

        save_user_flags(self.request, provided_job_info_flag)
        return super().form_valid(form)
