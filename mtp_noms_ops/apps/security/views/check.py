from django.contrib import messages
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import gettext_lazy
from django.views.generic.edit import FormView
from mtp_common.api import retrieve_all_pages_for_path

from security.forms.check import AcceptOrRejectCheckForm, CheckListForm, CreditsHistoryListForm
from security.utils import convert_date_fields
from security.views.object_base import SecurityView


class CheckListView(SecurityView):
    """
    View returning the checks in 'To action' (pending) status.
    """
    title = gettext_lazy('Credits to action')
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
    View rejecting a check in 'to action' (pending) status.
    """
    object_list_context_key = 'checks'

    title = gettext_lazy('Review credit')
    list_title = gettext_lazy('Credits to action')
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

        detail_object = context_data['form'].get_object()
        if not detail_object:
            raise Http404('Credit to check not found')

        api_session = context_data['form'].session

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
        # Get the credits from the same sender that were actioned by FIU
        if detail_object['credit']['sender_profile']:
            sender_response = retrieve_all_pages_for_path(
                api_session,
                f'/senders/{detail_object["credit"]["sender_profile"]}/credits/',
                **{
                    'exclude_credit__in': detail_object['credit']['id'],
                    'security_check__isnull': False,
                    'only_completed': False,
                    'security_check__actioned_by__isnull': False,
                    'include_checks': True
                }
            )
        else:
            sender_response = []
        sender_credits = convert_date_fields(sender_response, include_nested=True)

        # Get the credits to the same prisoner that were actioned by FIU
        if detail_object['credit']['prisoner_profile']:
            prisoner_response = retrieve_all_pages_for_path(
                api_session,
                f'/prisoners/{detail_object["credit"]["prisoner_profile"]}/credits/',
                **{
                    # Exclude any credits displayed as part of sender credits, to prevent duplication where
                    # both prisoner and sender same as the credit in question
                    'exclude_credit__in': ','.join(
                        [str(detail_object['credit']['id'])] + [str(c['id']) for c in sender_credits]
                    ),
                    'security_check__isnull': False,
                    'only_completed': False,
                    'security_check__actioned_by__isnull': False,
                    'include_checks': True
                }
            )
        else:
            prisoner_response = []
        prisoner_credits = convert_date_fields(prisoner_response, include_nested=True)

        return sorted(
            prisoner_credits + sender_credits,
            key=lambda c: c['security_check']['actioned_at'],
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
