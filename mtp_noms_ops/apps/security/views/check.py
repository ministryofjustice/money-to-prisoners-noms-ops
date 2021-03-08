from typing import Optional

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy
from django.views.generic.edit import BaseFormView, FormView
from mtp_common.api import retrieve_all_pages_for_path

from security.forms.check import (
    AutoAcceptDetailForm,
    AutoAcceptListForm,
    AcceptOrRejectCheckForm,
    CheckListForm,
    CreditsHistoryListForm,
    AssignCheckToUserForm,
    UserCheckListForm
)
from security.utils import convert_date_fields, get_abbreviated_cardholder_names
from security.views.object_base import SecurityView, SimpleSecurityDetailView


class CheckListView(SecurityView):
    """
    View returning the checks in 'To action' (pending) status.
    """
    title = gettext_lazy('Credits to action')
    template_name = 'security/checks_list.html'
    form_class = CheckListForm


class MyListCheckView(SecurityView):
    """
    View returning the checks in 'To action' (pending) status assigned to current user
    """
    title = gettext_lazy('My list')
    template_name = 'security/checks_list.html'
    form_class = UserCheckListForm


class CreditsHistoryListView(SecurityView):
    """
    View history of all accepted and rejected credits.
    """
    title = gettext_lazy('Decision history')
    template_name = 'security/credits_history_list.html'
    form_class = CreditsHistoryListForm


class AutoAcceptRuleListView(SecurityView):
    """
    View history of all auto-accept rules
    """
    title = gettext_lazy('Auto accepts')
    template_name = 'security/auto_accept_rule_list.html'
    form_class = AutoAcceptListForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['request_params'] = self.request.GET.dict()
        return context


class AutoAcceptRuleDetailView(SimpleSecurityDetailView, FormView):
    """
    View history of all auto-accept rules
    """
    list_title = gettext_lazy('Auto accepts')
    template_name = 'security/auto_accept_rule.html'
    object_context_key = 'auto_accept_rule'
    id_kwarg_name = 'auto_accept_rule_id'
    list_url = reverse_lazy('security:auto_accept_rule_list')
    success_url = reverse_lazy('security:auto_accept_rule_list')
    form_class = AutoAcceptDetailForm

    def get_form_kwargs(self):
        return dict(super().get_form_kwargs(), request=self.request, object_id=self.kwargs[self.id_kwarg_name])

    def get_object_request_params(self):
        return {
            'url': f'/security/checks/auto-accept/{self.kwargs[self.id_kwarg_name]}/'
        }

    def get_title_for_object(self, detail_object):
        return '{} {} {} {}'.format(
            gettext_lazy('Review auto accept of credits from'),
            get_abbreviated_cardholder_names(detail_object['debit_card_sender_details']['cardholder_names']),
            gettext_lazy('to'),
            detail_object['prisoner_profile']['prisoner_name']
        )

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        if not self.object:
            # raise a generic error to display standard 500 page if auto-accept rule failed to load for some reason
            raise ValueError('Could not load auto-accept rule')

        self.title = self.get_title_for_object(self.object)

        context_data['auto_accept_rule_is_active'] = sorted(
            self.object['states'],
            key=lambda s: s['created'],
            reverse=True
        )[0]['active']

        # These must be called again even though called from base class,
        # as they rely on self.title being populated, which in this case
        # requires the detail_object
        list_url = self.get_list_url()
        context_data['breadcrumbs'] = self.get_breadcrumbs(list_url)
        return context_data

    def get_breadcrumbs(self, list_url):
        return [
            {'name': gettext_lazy('Home'), 'url': reverse('security:dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': gettext_lazy('Review')},
        ]

    def get_object_for_template(self, obj):
        return convert_date_fields(obj, include_nested=True)

    def form_valid(self, form):
        result = form.deactivate_auto_accept_rule()
        if not result:
            return self.form_invalid(form)

        messages.add_message(
            self.request,
            messages.INFO,
            gettext_lazy('Auto accept rule was deactivated'),
        )
        return super().form_valid(form)


class CheckAssignView(BaseFormView):
    """
    Modify assignment of check
    """
    form_class = AssignCheckToUserForm
    redirect_to_list = False
    id_kwarg_name = 'check_id'
    page_kwarg_name = 'page'

    def get_success_url(self):
        check_id = self.kwargs[self.id_kwarg_name]
        if self.redirect_to_list:
            page = self.kwargs[self.page_kwarg_name]
            page_params = f'?page={page}#check-row-{check_id}'
            return reverse('security:check_list') + page_params
        else:
            return reverse('security:resolve_check', kwargs={'check_id': check_id})

    def get_form_kwargs(self):
        check_id = self.kwargs[self.id_kwarg_name]
        form_kwargs = super().get_form_kwargs()
        form_kwargs.update(
            request=self.request,
            object_id=check_id,
        )
        return form_kwargs

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(self.get_success_url())

    def form_valid(self, form):
        check_id = self.kwargs[self.id_kwarg_name]
        result = form.assign_or_unassign()
        if not result:
            if self.redirect_to_list:
                return HttpResponseRedirect(reverse('security:check_list'))
            else:
                return HttpResponseRedirect(
                    reverse('security:resolve_check', kwargs={'check_id': check_id})
                )

        return super().form_valid(form)


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

    @staticmethod
    def get_latest_auto_accept_state(auto_accept_rule):
        return sorted(
            auto_accept_rule['states'], key=lambda x: x['created']
        )[-1]

    def get_unbound_active_auto_accept_state(
        self, api_session, debit_card_sender_details_id: int, prisoner_profile_id: int
    ) -> Optional[dict]:
        query_existing_auto_accept_rule = api_session.get(
            '/security/checks/auto-accept',
            params={
                'prisoner_profile_id': prisoner_profile_id,
                'debit_card_sender_details_id': debit_card_sender_details_id
            }
        )

        payload = query_existing_auto_accept_rule.json().get('results')
        if len(payload) == 1 and self.get_latest_auto_accept_state(payload[0]).get('active'):
            return convert_date_fields(self.get_latest_auto_accept_state(payload[0]))

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        detail_object = context_data['form'].get_object()
        if not detail_object:
            raise Http404('Credit to check not found')

        api_session = context_data['form'].session
        context_data['unbound_active_auto_accept_state'] = self.get_unbound_active_auto_accept_state(
            api_session,
            detail_object['credit']['billing_address'][
                'debit_card_sender_details'
            ],
            detail_object['credit']['prisoner_profile'],
        )

        # keep query string in breadcrumbs
        list_url = self.request.build_absolute_uri(str(self.list_url))
        referrer_url = self.request.META.get('HTTP_REFERER', '-')
        if referrer_url.split('?', 1)[0] == list_url:
            list_url = referrer_url

        context_data['breadcrumbs'] = [
            {'name': gettext_lazy('Home'), 'url': reverse('security:dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': self.title}
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
            result, additional_info_message = form.accept_or_reject()

            if not result:
                return self.form_invalid(form)
            if additional_info_message:
                messages.add_message(
                    self.request,
                    messages.INFO,
                    gettext_lazy(additional_info_message),
                )

            if form.data['fiu_action'] == 'accept':
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
