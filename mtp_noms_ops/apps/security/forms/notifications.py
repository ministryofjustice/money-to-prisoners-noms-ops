import datetime
from math import ceil

from django.utils.dateparse import parse_date
from django.utils.translation import gettext_lazy as _

from security.forms.base import SecurityForm, validate_range_fields
from security.utils import convert_date_fields, sender_profile_name


@validate_range_fields(
    ('triggered_at', _('Must be after the start date'), '__lt'),
)
class NotificationsForm(SecurityForm):
    # NB: ensure that these templates are HTML-safe
    filtered_description_template = 'All notifications are shown below.'
    unfiltered_description_template = 'All notifications are shown below.'
    description_templates = ()

    page_size = 25

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        self.date_count = 0

    def get_object_list_endpoint_path(self):
        return '/events/'

    def get_query_data(self, allow_parameter_manipulation=True):
        query_data = super().get_query_data(allow_parameter_manipulation=allow_parameter_manipulation)
        if allow_parameter_manipulation:
            query_data['rule'] = ('MONP', 'MONS')
        return query_data

    def get_api_request_page_params(self):
        filters = super().get_api_request_page_params()
        if filters is not None:
            data = self.session.get('/events/pages/', params=filters).json()
            self.date_count = data['count']
            filters['ordering'] = '-triggered_at'
            del filters['offset']
            del filters['limit']
            if data['newest']:
                filters['triggered_at__lt'] = parse_date(data['newest']) + datetime.timedelta(days=1)
                filters['triggered_at__gte'] = parse_date(data['oldest'])
        return filters

    def get_object_list(self):
        events = convert_date_fields(super().get_object_list())
        date_groups = map(summarise_date_group, group_events_by_date(events))

        self.page_count = int(ceil(self.date_count / self.page_size))
        self.total_count = self.date_count
        return date_groups


def make_date_group(date):
    return {
        'date': date,
        'senders': {},
        'prisoners': {},
    }


def make_date_group_profile(profile_id, description):
    return {
        'id': profile_id,
        'description': description,
        'credit_ids': set(),
        'disbursement_ids': set(),
    }


def group_events_by_date(events):
    date_groups = []
    date_group = make_date_group(None)
    for event in events:
        event_date = event['triggered_at'].date()
        if event_date != date_group['date']:
            date_group = make_date_group(event_date)
            date_groups.append(date_group)

        if event['sender_profile']:
            profile = event['sender_profile']
            if profile['id'] in date_group['senders']:
                details = date_group['senders'][profile['id']]
            else:
                details = make_date_group_profile(
                    profile['id'],
                    sender_profile_name(profile)
                )
                date_group['senders'][profile['id']] = details
            if event['credit_id']:
                details['credit_ids'].add(event['credit_id'])
            if event['disbursement_id']:
                details['disbursement_ids'].add(event['disbursement_id'])

        if event['prisoner_profile']:
            profile = event['prisoner_profile']
            if profile['id'] in date_group['prisoners']:
                details = date_group['prisoners'][profile['id']]
            else:
                details = make_date_group_profile(
                    profile['id'],
                    f"{profile['prisoner_name']} ({profile['prisoner_number']})"
                )
                date_group['prisoners'][profile['id']] = details
            if event['credit_id']:
                details['credit_ids'].add(event['credit_id'])
            if event['disbursement_id']:
                details['disbursement_ids'].add(event['disbursement_id'])
    return date_groups


def summarise_date_group(date_group):
    date_group_transaction_count = 0

    sender_summaries = []
    senders = sorted(
        date_group['senders'].values(),
        key=lambda s: s['description']
    )
    for sender in senders:
        profile_transaction_count = len(sender['credit_ids'])
        date_group_transaction_count += profile_transaction_count
        sender_summaries.append({
            'id': sender['id'],
            'transaction_count': profile_transaction_count,
            'description': sender['description'],
        })

    prisoner_summaries = []
    prisoners = sorted(
        date_group['prisoners'].values(),
        key=lambda p: p['description']
    )
    for prisoner in prisoners:
        disbursements_only = bool(prisoner['disbursement_ids'] and not prisoner['credit_ids'])
        profile_transaction_count = len(prisoner['credit_ids']) + len(prisoner['disbursement_ids'])
        date_group_transaction_count += profile_transaction_count
        prisoner_summaries.append({
            'id': prisoner['id'],
            'transaction_count': profile_transaction_count,
            'description': prisoner['description'],
            'disbursements_only': disbursements_only,
        })

    return {
        'date': date_group['date'],
        'transaction_count': date_group_transaction_count,
        'senders': sender_summaries,
        'prisoners': prisoner_summaries,
    }
