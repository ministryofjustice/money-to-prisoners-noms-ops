import collections
import datetime
import re

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext
from mtp_common.auth import USER_DATA_SESSION_KEY
from mtp_common.auth.api_client import get_api_session

from . import (
    prison_choice_pilot_flag, hmpps_employee_flag, confirmed_prisons_flag,
    notifications_pilot_flag
)


def and_join(values):
    if len(values) > 1:
        values = values[:-2] + [gettext('%s and %s') % (values[-2], values[-1])]
    return ', '.join(values)


def parse_date_fields(object_list):
    """
    MTP API responds with string date/time fields, this filter converts them to python objects
    """
    fields = ('received_at', 'credited_at', 'refunded_at', 'created')
    parsers = (parse_datetime, parse_date)

    def convert(credit):
        for field in fields:
            value = credit.get(field)
            if not value or not isinstance(value, str):
                continue
            for parser in parsers:
                try:
                    value = parser(value)
                    if isinstance(value, datetime.datetime):
                        value = timezone.localtime(value)
                    credit[field] = value
                    break
                except (ValueError, TypeError):
                    pass
        return credit

    return list(map(convert, object_list)) if object_list else object_list


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
    in_pilot = prison_choice_pilot_flag in user.user_data.get('flags', [])
    has_only_security_roles = user.user_data['roles'] == ['security']
    is_user_admin = user.has_perm('auth.change_user')
    return in_pilot and has_only_security_roles and not is_user_admin


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


def can_skip_confirming_prisons(user):
    already_confirmed = confirmed_prisons_flag in user.user_data.get('flags', [])
    cannot_choose_prisons = not can_choose_prisons(user)
    return already_confirmed or cannot_choose_prisons


def can_see_notifications(user):
    return (
        user.is_authenticated and
        notifications_pilot_flag in user.user_data.get('flags', [])
    )


def is_nomis_api_configured():
    return (
        settings.NOMIS_API_BASE_URL and
        settings.NOMIS_API_CLIENT_TOKEN and
        settings.NOMIS_API_PRIVATE_KEY
    )
