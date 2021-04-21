import collections
import datetime
import logging
import re

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext_lazy as _
from mtp_common.auth import USER_DATA_SESSION_KEY
from mtp_common.auth.api_client import get_api_session

from security import hmpps_employee_flag, confirmed_prisons_flag, provided_job_info_flag

logger = logging.getLogger('mtp')


def get_need_attention_date():
    """
    Gets the cutoff datetime before which a payment is considered needing attention.
    Now treats checks that would need attention today (before midnight) as needing attention now
    so that the count will not vary throughout the day.

    Idea: Could alternatively consider (9am the next working day - URGENT_IF_OLDER_THAN) as needs attention cutoff
    in order to account for long weekends and holidays.
    """
    urgent_if_older_than = datetime.timedelta(days=3)

    tomorrow = timezone.now() + datetime.timedelta(days=1)
    tomorrow = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    return tomorrow - urgent_if_older_than


def convert_date_fields(object_list, include_nested=False):
    """
    MTP API responds with string date/time fields, this filter converts them to python objects.
    `object_list` can be either a list or a single object.
    If `include_nested` is True, it will also convert values in nested dicts, nested lists are not
    supported yet.
    """
    fields = ('started_at', 'received_at', 'credited_at', 'refunded_at', 'created', 'triggered_at', 'actioned_at')
    parsers = (parse_datetime, parse_date)

    def convert(obj):
        if include_nested:
            for field, value in obj.items():
                if isinstance(value, dict):
                    obj[field] = convert(value)
                elif isinstance(value, list):
                    obj[field] = [
                        convert(element)
                        if isinstance(element, dict)
                        else element
                        for element in value
                    ]

        for field in fields:
            value = obj.get(field)
            if not value or not isinstance(value, str):
                continue
            for parser in parsers:
                try:
                    new_value = parser(value)
                    if not new_value:
                        continue

                    if isinstance(new_value, datetime.datetime):
                        new_value = timezone.localtime(new_value)
                    obj[field] = new_value
                    break
                except (ValueError, TypeError):
                    logger.exception('Failed to convert date fields in object list')
        return obj

    if isinstance(object_list, dict):
        return convert(object_list)

    return list(map(convert, object_list)) if object_list else object_list


def sender_profile_name(sender):
    try:
        return sender['bank_transfer_details'][0]['sender_name']
    except (KeyError, IndexError):
        pass
    try:
        return sender['debit_card_details'][0]['cardholder_names'][0]
    except (KeyError, IndexError):
        pass
    return _('Unknown sender')


class OrderedSet(collections.MutableSet):
    def __init__(self, iterable=None):
        super().__init__()
        self.item_list = []
        self.item_set = set()
        if iterable:
            self.extend(iterable)

    def __repr__(self):
        return repr(self.item_list)

    def __len__(self):
        return len(self.item_list)

    def __iter__(self):
        return iter(self.item_list)

    def __contains__(self, item):
        item_hash = self.hash_item(item)
        return item_hash in self.item_set

    def __getitem__(self, index):
        return self.item_list[index]

    def add(self, item):
        item_hash = self.hash_item(item)
        if item_hash not in self.item_set:
            self.item_list.append(item)
            self.item_set.add(item_hash)

    def extend(self, iterable):
        for item in iterable:
            self.add(item)

    def discard(self, item):
        item_hash = self.hash_item(item)
        self.item_list.remove(item)
        self.item_set.remove(item_hash)

    def pop_first(self):
        item = self.item_list.pop(0)
        item_hash = self.hash_item(item)
        self.item_set.remove(item_hash)
        return item

    def hash_item(self, item):
        raise NotImplementedError


class NameSet(OrderedSet):
    """
    An ordered set of names: adding a name will not modify it,
    but if a similar one already exists, the new one is not added
    """
    whitespace = re.compile(r'\s+')
    titles = {'miss', 'mrs', 'mr', 'dr'}

    def __init__(self, iterable=None, strip_titles=False):
        self.strip_titles = strip_titles
        super().__init__(iterable=iterable)

    def hash_item(self, item):
        name = self.whitespace.sub(' ', (item or '').strip()).lower()
        if self.strip_titles:
            for title_prefix in (t for title in self.titles for t in ('%s ' % title, '%s. ' % title)):
                if name.startswith(title_prefix):
                    return name[len(title_prefix):]
        return name


class EmailSet(OrderedSet):
    """
    An ordered set of email addresses: adding an email will not modify it,
    but if a similar one already exists, the new one is not added
    """

    def hash_item(self, item):
        return (item or '').strip().lower()


def can_choose_prisons(user):
    has_only_security_roles = user.user_data['roles'] == ['security']
    is_user_admin = user.has_perm('auth.change_user')
    return has_only_security_roles and not is_user_admin


def save_user_flags(request, flag, api_session=None):
    api_session = api_session or get_api_session(request)
    api_session.put('/users/%s/flags/%s/' % (request.user.username, flag), json={})
    flags = set(request.user.user_data.get('flags') or [])
    flags.add(flag)
    flags = list(flags)
    request.user.user_data['flags'] = flags
    request.session[USER_DATA_SESSION_KEY] = request.user.user_data


def refresh_user_data(request, api_session=None):
    api_session = api_session or get_api_session(request)
    user = request.user
    user.user_data = api_session.get(
        '/users/{username}/'.format(username=user.username)
    ).json()
    request.session[USER_DATA_SESSION_KEY] = user.user_data


def is_hmpps_employee(user):
    flags = user.user_data.get('flags') or []
    return hmpps_employee_flag in flags


def has_provided_job_information(user):
    flags = user.user_data.get('flags') or []
    return provided_job_info_flag in flags


def can_skip_confirming_prisons(user):
    flags = user.user_data.get('flags') or []
    already_confirmed = confirmed_prisons_flag in flags
    cannot_choose_prisons = not can_choose_prisons(user)
    return already_confirmed or cannot_choose_prisons


def can_manage_security_checks(user):
    return user.has_perms(
        ('security.view_check', 'security.change_check'),
    )


def remove_whitespaces_and_hyphens(value):
    """
    Returns value without whitespaces or -
    """
    if not value:
        return value
    return re.sub(r'[\s-]+', '', value)


def get_abbreviated_cardholder_names(cardholder_names):
    if len(cardholder_names) == 2:
        return _('%(cardholder_name)s and 1 more name' % {'cardholder_name': cardholder_names[0]})
    elif len(cardholder_names) >= 2:
        return _('%(cardholder_name)s and %(number_of_remaining_names)s more names' % {
            'cardholder_name': cardholder_names[0], 'number_of_remaining_names': len(cardholder_names) - 1
        })
    else:
        return cardholder_names[0]
