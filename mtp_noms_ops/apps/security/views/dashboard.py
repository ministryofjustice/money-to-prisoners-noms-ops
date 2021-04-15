import logging

from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext, ngettext
from django.views.generic import TemplateView
from mtp_common.auth.api_client import get_api_session
from requests.exceptions import RequestException

from security.context_processors import initial_params
from security.searches import get_saved_searches, populate_new_result_counts


logger = logging.getLogger('mtp')


class DashboardView(TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        kwargs.update({
            'start_page_url': settings.START_PAGE_URL,
            'link_cards': self.get_link_cards(),
            'saved_search_cards': self.get_saved_search_cards(),
            'admin_cards': self.get_admin_cards(),
            'user_request_count': self.get_user_request_count(),
        })
        return super().get_context_data(**kwargs)

    def get_user_request_count(self) -> int:
        if self.request.user.has_perm('auth.change_user'):
            try:
                api_session = get_api_session(self.request)
                response = api_session.get('requests/', params={'page_size': 1})
                return response.json().get('count', 0)
            except RequestException:
                logger.exception('Failed to get number of account requests')

        return 0

    def get_link_cards(self):
        if not self.request.can_access_security:
            return []
        prisons_param = initial_params(self.request).get('initial_params', '')
        prisons_param = f'?{prisons_param}'
        cards = [
            {
                'heading': gettext('Prisoners'),
                'link': reverse('security:prisoner_list') + prisons_param,
            },
            {
                'heading': gettext('Payment sources'),
                'link': reverse('security:sender_list') + prisons_param,
            },
            {
                'heading': gettext('Credits'),
                'link': reverse('security:credit_list') + prisons_param,
            },
            {
                'heading': gettext('Disbursements'),
                'link': reverse('security:disbursement_list') + prisons_param,
            },
            {
                'heading': gettext('Notifications'),
                'link': reverse('security:notification_list'),
            },
        ]
        if self.request.can_manage_security_checks:
            cards.append({
                'heading': gettext('Credits to action'),
                'link': reverse('security:check_list'),
            })
        return cards

    def get_saved_search_cards(self):
        if not self.request.can_access_security:
            return []
        session = get_api_session(self.request)
        saved_searches = populate_new_result_counts(session, get_saved_searches(session))
        return [
            {
                'heading': search['description'],
                'link': search['site_url'],
                'description': (
                    ngettext('%d new credit', '%d new credits', search['new_result_count']) % search['new_result_count']
                    if search.get('new_result_count')
                    else ''
                )
            }
            for search in saved_searches
        ]

    def get_admin_cards(self):
        cards = []
        if self.request.can_access_security and self.request.can_pre_approve:
            cards.append({
                'heading': gettext('New credits check'),
                'link': reverse('security:review_credits'),
            })
        if self.request.can_access_user_management:
            cards.append({
                'heading': gettext('Manage users'),
                'link': reverse('list-users'),
            })
        if self.request.can_access_prisoner_location:
            cards.append({
                'heading': gettext('Upload prisoner location file'),
                'link': reverse('location_file_upload'),
            })
        return cards
