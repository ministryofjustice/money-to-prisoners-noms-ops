from datetime import timedelta
from math import ceil

from django.conf import settings
from django.core.urlresolvers import reverse_lazy
from django.shortcuts import redirect
from django.utils.dateparse import parse_date
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from mtp_common.auth.api_client import get_api_session
from requests.exceptions import RequestException

from security.utils import (
    populate_totals, parse_date_fields, can_see_notifications
)


class NotificationListView(TemplateView):
    title = _('Notifications')
    template_name = 'security/notifications.html'
    page_size = 20

    def dispatch(self, request, *args, **kwargs):
        if not can_see_notifications(request.user):
            return redirect(reverse_lazy(settings.LOGIN_REDIRECT_URL))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        week_start = parse_date(self.kwargs.get('week_start', ''))
        if week_start is None:
            week_start = now().date()
        week_start = week_start - timedelta(days=week_start.weekday())
        context['current_week'] = week_start
        context['previous_week'] = week_start - timedelta(days=7)
        next_week = week_start + timedelta(days=7)
        if next_week <= now().date():
            context['next_week'] = next_week
        self.populate_notifications(get_api_session(self.request), context)
        return context

    def populate_notifications(self, session, context):
        self.notification_total = 0
        start_date = context['current_week'],
        end_date = context['current_week'] + timedelta(days=7)
        prison_filter = ','.join(p['nomis_id'] for p in self.request.user_prisons)
        context['monitored_credits'] = self.get_credit_list(
            session,
            'monitored_credits_page',
            monitored=True,
            received_at__gte=start_date,
            received_at__lt=end_date
        )
        context['monitored_disbursements'] = self.get_disbursement_list(
            session,
            'monitored_disbursements_page',
            monitored=True,
            created__gte=start_date,
            created__lt=end_date
        )
        context['not_whole_credits'] = self.get_event_list(
            session,
            'not_whole_credits_page',
            rule='NWN',
            for_credit=True,
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            credit_prison=prison_filter
        )
        context['not_whole_disbursements'] = self.get_event_list(
            session,
            'not_whole_disbursements_page',
            rule='NWN',
            for_disbursement=True,
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            disbursement_prison=prison_filter
        )
        context['high_amount_credits'] = self.get_event_list(
            session,
            'high_amount_credits_page',
            rule='HA',
            for_credit=True,
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            credit_prison=prison_filter
        )
        context['high_amount_disbursements'] = self.get_event_list(
            session,
            'high_amount_disbursements_page',
            rule='HA',
            for_disbursement=True,
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            disbursement_prison=prison_filter
        )
        context['frequent_senders'] = self.get_event_list(
            session,
            'frequent_senders_page',
            rule='CSFREQ',
            group_by='sender_profile',
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            credit_prison=prison_filter
        )
        context['frequent_recipients'] = self.get_event_list(
            session,
            'frequent_recipients_page',
            rule='DRFREQ',
            group_by='recipient_profile',
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            disbursement_prison=prison_filter
        )
        context['from_many_senders'] = self.get_event_list(
            session,
            'from_many_senders_page',
            rule='CSNUM',
            group_by='prisoner_profile',
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            credit_prison=prison_filter
        )
        context['to_many_recipients'] = self.get_event_list(
            session,
            'to_many_recipients_page',
            rule='DRNUM',
            group_by='prisoner_profile',
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            disbursement_prison=prison_filter
        )
        context['to_many_prisoners'] = self.get_event_list(
            session,
            'to_many_prisoners_page',
            rule='CPNUM',
            group_by='sender_profile',
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            credit_prison=prison_filter
        )
        context['from_many_prisoners'] = self.get_event_list(
            session,
            'from_many_prisoners_page',
            rule='DPNUM',
            group_by='recipient_profile',
            triggered_at__gte=start_date,
            triggered_at__lt=end_date,
            disbursement_prison=prison_filter
        )
        return context

    def get_event_list(self, session, page_param, **filters):
        event_list = self.get_object_list(
            '/events', session, page_param, ordering='-triggered_at', **filters
        )
        for event in event_list['results']:
            if 'group_by' in filters:
                populate_totals(event[filters['group_by']], 'last_4_weeks')
        return event_list

    def get_credit_list(self, session, page_param, **filters):
        return self.get_object_list('/credits', session, page_param, **filters)

    def get_disbursement_list(self, session, page_param, **filters):
        return self.get_object_list('/disbursements', session, page_param, **filters)

    def get_object_list(self, path, session, page_param, **filters):
        page = int(self.request.GET.get(page_param, 1))
        offset = (page - 1) * self.page_size
        filters = {k: v for k, v in filters.items() if v}
        try:
            data = session.get(
                path,
                params=dict(offset=offset, limit=self.page_size, **filters)
            ).json()
        except RequestException:
            return {
                'results': [],
                'total_count': 0,
                'page_count': 0,
                'page': page
            }
        total_count = data.get('count', 0)
        page_count = int(ceil(total_count / self.page_size))
        self.notification_total += total_count
        return {
            'results': parse_date_fields(data.get('results', [])),
            'total_count': total_count,
            'page_count': page_count,
            'page': page,
            'page_param': page_param
        }
