from typing import Optional

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import BaseFormView, FormView

from security.constants import SECURITY_FORMS_DEFAULT_PAGE_SIZE
from security.forms.check import (
    AutoAcceptDetailForm,
    AutoAcceptListForm,
    AcceptOrRejectCheckForm,
    CheckListForm,
    CheckHistoryForm,
    AssignCheckToUserForm,
    UserCheckListForm,
)
from security.utils import convert_date_fields, get_abbreviated_cardholder_names
from security.views.object_base import SecurityView, SimpleSecurityDetailView


class CheckListView(SecurityView):
    """
    View returning the checks in 'To action' (pending) status.
    """
    title = _('Credits to action')
    template_name = 'security/check_list.html'
    form_class = CheckListForm


class MyCheckListView(SecurityView):
    """
    View returning the checks in 'To action' (pending) status assigned to current user
    """
    title = _('My list')
    template_name = 'security/check_list.html'
    form_class = UserCheckListForm


class CheckHistoryListView(SecurityView):
    """
    View history of all accepted and rejected credits.
    """
    title = _('Decision history')
    template_name = 'security/check_history_list.html'
    form_class = CheckHistoryForm


class AutoAcceptRuleListView(SecurityView):
    """
    View history of all auto-accept rules
    """
    title = _('Auto accepts')
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
    list_title = _('Auto accepts')
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
        return _('Review auto accept of credits from %(sender)s to %(prisoner)s') % {
            'sender': get_abbreviated_cardholder_names(detail_object['debit_card_sender_details']['cardholder_names']),
            'prisoner': detail_object['prisoner_profile']['prisoner_name'],
        }

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
            {'name': _('Home'), 'url': reverse('security:dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': _('Review')},
        ]

    def get_object_for_template(self, obj):
        return convert_date_fields(obj, include_nested=True)

    def form_valid(self, form):
        result = form.deactivate_auto_accept_rule()
        if not result:
            return self.form_invalid(form)

        messages.info(self.request, _('The auto accept was stopped'))
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

    title = _('Review credit')
    list_title = _('Credits to action')
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
                'initial': {
                    'redirect_url': self.request.GET.get('redirect_url', ''),
                },
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
            {'name': _('Home'), 'url': reverse('security:dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': self.title}
        ]
        context_data[self.object_context_key] = detail_object
        related_credits, likely_truncated = self.get_related_credits(api_session, context_data[self.object_context_key])
        context_data['related_credits'] = related_credits
        context_data['likely_truncated'] = likely_truncated
        return context_data

    @classmethod
    def get_related_credits(cls, api_session, detail_object):
        likely_truncated = False

        # Get the credits from the same sender that were actioned by FIU
        if detail_object['credit']['sender_profile']:
            response = api_session.get(
                f'/senders/{detail_object["credit"]["sender_profile"]}/credits/',
                params=dict(
                    limit=SECURITY_FORMS_DEFAULT_PAGE_SIZE, offset=0,
                    exclude_credit__in=detail_object['credit']['id'],
                    security_check__isnull=False,
                    only_completed=False,
                    security_check__actioned_by__isnull=False,
                    include_checks=True,
                ),
            ).json()
            sender_response = response.get('results') or []
            likely_truncated |= response.get('count') and response['count'] > len(sender_response)
        else:
            sender_response = []
        sender_credits = convert_date_fields(sender_response, include_nested=True)

        # Get the credits to the same prisoner that were actioned by FIU
        if detail_object['credit']['prisoner_profile']:
            response = api_session.get(
                f'/prisoners/{detail_object["credit"]["prisoner_profile"]}/credits/',
                params=dict(
                    limit=SECURITY_FORMS_DEFAULT_PAGE_SIZE, offset=0,
                    # Exclude any credits displayed as part of sender credits, to prevent duplication where
                    # both prisoner and sender same as the credit in question
                    exclude_credit__in=','.join(
                        [str(detail_object['credit']['id'])] + [str(c['id']) for c in sender_credits]
                    ),
                    security_check__isnull=False,
                    only_completed=False,
                    security_check__actioned_by__isnull=False,
                    include_checks=True,
                ),
            ).json()
            prisoner_response = response.get('results') or []
            likely_truncated |= response.get('count') and response['count'] > len(prisoner_response)
        else:
            prisoner_response = []
        prisoner_credits = convert_date_fields(prisoner_response, include_nested=True)

        return sorted(
            prisoner_credits + sender_credits,
            key=lambda c: c['security_check']['actioned_at'],
            reverse=True
        ), likely_truncated

    def form_valid(self, form):
        if self.request.method == 'POST':
            result, additional_info_message = form.accept_or_reject()
            if not result:
                return self.form_invalid(form)
            if additional_info_message:
                messages.info(self.request, additional_info_message)

            if form.data['fiu_action'] == 'accept':
                ui_message = _('Credit accepted')
            else:
                ui_message = _('Credit rejected')
            messages.info(self.request, ui_message)

            redirect_url = form.cleaned_data['redirect_url']
            if not url_has_allowed_host_and_scheme(
                url=redirect_url,
                allowed_hosts={self.request.get_host()},
                require_https=self.request.is_secure(),
            ):
                redirect_url = self.list_url
            return HttpResponseRedirect(redirect_url)

        return super().form_valid(form)
