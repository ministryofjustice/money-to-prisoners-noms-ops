from urllib.parse import urlencode

from django.core.urlresolvers import reverse_lazy
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from mtp_common.auth.api_client import get_api_session

from security import confirmed_prisons_flag
from security.utils import (
    save_user_flags, can_skip_confirming_prisons, can_see_notifications
)
from settings.forms import ConfirmPrisonForm, ChangePrisonForm, ALL_PRISONS_CODE


class NomsOpsSettingsView(TemplateView):
    title = _('Settings')
    template_name = 'settings/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = get_api_session(self.request)
        if can_see_notifications(self.request.user):
            context['email_notifications'] = False
            email_preferences = session.get('/emailpreferences').json()
            context['email_notifications'] = email_preferences['frequency'] == 'weekly'
        return context

    def post(self, *args, **kwargs):
        if 'submit_email_preferences' in self.request.POST:
            session = get_api_session(self.request)
            if 'toggle' in self.request.POST:
                session.post('/emailpreferences', json={'frequency': 'weekly'})
            else:
                session.post('/emailpreferences', json={'frequency': 'never'})
        return redirect(reverse_lazy('settings'))


class ConfirmPrisonsView(FormView):
    title = _('Confirm your prisons')
    template_name = 'settings/confirm-prisons.html'
    form_class = ConfirmPrisonForm
    success_url = reverse_lazy('confirm_prisons_confirmation')

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
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
        context['can_navigate_away'] = can_skip_confirming_prisons(self.request.user)
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


class ChangePrisonsView(FormView):
    title = _('Change prisons')
    template_name = 'settings/confirm-prisons-change.html'
    form_class = ChangePrisonForm
    success_url = reverse_lazy('settings')

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['data_attrs'] = {
            'data-autocomplete-error-empty': _('Type a prison name'),
            'data-autocomplete-error-summary': _('There was a problem'),
            'data-event-category': 'PrisonConfirmation',
        }
        context['current_prisons'] = ','.join([
            p['nomis_id'] for p in self.request.user.user_data['prisons']
        ] if self.request.user.user_data.get('prisons') else ['ALL'])
        context['can_navigate_away'] = True
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

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['can_navigate_away'] = can_skip_confirming_prisons(self.request.user)
        return context

    def form_valid(self, form):
        return redirect('{path}?{query}'.format(
            path=self.get_success_url(),
            query=form.get_confirmation_query_string()
        ))


class ConfirmPrisonsConfirmationView(TemplateView):
    title = _('Your prisons have been saved')
    template_name = 'settings/confirm-prisons-confirmation.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['prisons'] = self.request.user_prisons
        return context
