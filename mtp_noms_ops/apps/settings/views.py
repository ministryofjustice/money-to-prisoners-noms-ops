import logging
from urllib.parse import urlencode

from django.core.urlresolvers import reverse_lazy
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from mtp_common.auth.api_client import get_api_session

from security import confirmed_prisons_flag
from security.utils import save_user_flags, can_skip_confirming_prisons
from settings.forms import ChoosePrisonForm

logger = logging.getLogger('mtp')


class NomsOpsSettingsView(TemplateView):
    template_name = 'settings/settings.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        session = get_api_session(self.request)
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
    form_class = ChoosePrisonForm
    success_url = reverse_lazy('confirm_prisons_confirmation')

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['data_attrs'] = {
            'data-autocomplete-error-empty': _('Type a prison name'),
            'data-autocomplete-error-summary': _('There was a problem'),
            'data-event-category': 'ConfirmPrisons',
        }
        context['current_prisons'] = ','.join([
            p['nomis_id'] for p in self.request.user.user_data['prisons']
        ] if self.request.user.user_data.get('prisons') else ['ALL'])
        context['can_navigate_away'] = can_skip_confirming_prisons(self.request.user)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        if form.action == 'confirm':
            form.save()
            save_user_flags(self.request, confirmed_prisons_flag)
            return redirect(self.get_success_url())

        new_query_string = form.get_query_string()
        return redirect('{path}?{query}'.format(
            path=reverse_lazy('confirm_prisons'),
            query=new_query_string
        ))

    def get_success_url(self):
        if 'next' in self.request.GET:
            return '{path}?{query}'.format(
                path=self.success_url,
                query=urlencode({'next': self.request.GET['next']})
            )
        return self.success_url


class ConfirmPrisonsConfirmationView(TemplateView):
    title = _('Your prisons have been saved')
    template_name = 'settings/confirm-prisons-confirmation.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['prisons'] = self.request.user_prisons
        return context
