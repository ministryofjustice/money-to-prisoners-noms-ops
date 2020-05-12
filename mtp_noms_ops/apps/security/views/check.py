from urllib.parse import urlencode

from django.contrib import messages
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import gettext_lazy
from django.views.generic.edit import FormView
from mtp_common.auth.api_client import get_api_session

from security.forms.check import AcceptOrRejectCheckForm, CheckListForm, CreditsHistoryListForm
from security.views.object_base import SecurityView


class CheckListView(SecurityView):
    """
    View returning the checks in pending status.
    """
    title = gettext_lazy('Pending')
    template_name = 'security/checks_list.html'
    form_class = CheckListForm


class CreditsHistoryListView(SecurityView):
    """
    View history of all accepted and rejected credits.
    """
    title = gettext_lazy('Decision history')
    template_name = 'security/credits_history_list.html'
    form_class = CreditsHistoryListForm


class AcceptOrRejectCheckView(FormView):
    """
    View rejecting a check in pending status.
    """
    object_list_context_key = 'checks'

    title = gettext_lazy('Review pending credit')
    list_title = gettext_lazy('Credits pending')
    id_kwarg_name = 'check_id'
    object_context_key = 'check'
    list_url = reverse_lazy('security:check_list')
    template_name = 'security/accept_or_reject_check.html'
    form_class = AcceptOrRejectCheckForm

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs.update(
            {
                'request': self.request,
                'object_id': self.kwargs[self.id_kwarg_name],
            },
        )
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        api_session = get_api_session(self.request)

        detail_object = context_data['form'].get_object()
        if detail_object is None:
            raise Http404('Detail object not found')

        # keep query string in breadcrumbs
        list_url = self.request.build_absolute_uri(str(self.list_url))
        referrer_url = self.request.META.get('HTTP_REFERER', '-')
        if referrer_url.split('?', 1)[0] == list_url:
            list_url = referrer_url

        context_data['breadcrumbs'] = [
            {'name': gettext_lazy('Home'), 'url': reverse('security:dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': self.title},
        ]
        context_data[self.object_context_key] = detail_object
        context_data['related_credits'] = self._get_related_credits(api_session, context_data[self.object_context_key])
        return context_data

    @staticmethod
    def _get_related_credits(api_session, detail_object):
        # Get the sender credits
        sender_response = api_session.get(
            '/senders/{sender_profile_id}/credits/?{querystring}'.format(
                sender_profile_id=detail_object['credit']['sender_profile'],
                querystring=urlencode([
                    ('exclude_credit__in', detail_object['credit']['id']),
                    ('include_checks:', True)
                ])
            )
        )
        sender_response.raise_for_status()
        sender_credits = sender_response.json().get('results')

        prisoner_response = api_session.get(
            '/prisoners/{prisoner_profile_id}/credits/?{querystring}'.format(
                prisoner_profile_id=detail_object['credit']['prisoner_profile'],
                querystring=urlencode([
                    ('exclude_credit__in', detail_object['credit']['id']),
                    ('include_checks:', True)
                ])
            )
        )
        prisoner_response.raise_for_status()
        prisoner_credits = prisoner_response.json().get('results')

        return sorted(
            prisoner_credits + sender_credits,
            key=lambda c: c['started_at'],
            reverse=True
        )

    def form_valid(self, form):
        if self.request.method == 'POST':
            result = form.accept_or_reject()

            if not result:
                return self.form_invalid(form)

            if form.cleaned_data['fiu_action'] == 'accept':
                ui_message = gettext_lazy('Credit accepted')
            else:
                ui_message = gettext_lazy('Credit rejected')

            messages.add_message(
                self.request,
                messages.INFO,
                gettext_lazy(ui_message),
            )
            return HttpResponseRedirect(self.list_url)

        return super().form_valid(form)
