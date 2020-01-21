import collections
import datetime
import enum
import itertools
from math import ceil
import re
from urllib.parse import urlencode, urlparse, urljoin

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.dateformat import format as date_format
from django.utils.functional import cached_property
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _, override as override_locale
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.api import retrieve_all_pages_for_path
from mtp_common.auth.api_client import get_api_session
from mtp_common.auth.exceptions import HttpNotFoundError
from requests.exceptions import RequestException

from security.models import PrisonList
from security.searches import (
    save_search, update_result_count, delete_search, get_existing_search
)
from security.utils import convert_date_fields


def parse_amount(value, as_int=True):
    # assumes a valid amount in pounds, i.e. validate_amount passes
    value = value.lstrip('£')
    if '.' in value:
        value = value.replace('.', '')
    else:
        value += '00'
    if as_int:
        return int(value)
    return value


def validate_amount(amount):
    if not re.match(r'^£?\d+(\.\d\d)?$', amount):
        raise ValidationError(_('Invalid amount.'), code='invalid')


def validate_prisoner_number(prisoner_number):
    if not re.match(r'^[a-z]\d\d\d\d[a-z]{2}$', prisoner_number, flags=re.I):
        raise ValidationError(_('Invalid prisoner number.'), code='invalid')


def validate_range_fields(*fields):
    def inner(cls):
        base_clean = cls.clean

        def clean(self):
            base_clean(self)
            for field in fields:
                field_name, bound_ordering_msg, *upper_limit = field
                lower = field_name + '__gte'
                upper = field_name + (upper_limit[0] if upper_limit else '__lte')
                lower_value = self.cleaned_data.get(lower)
                upper_value = self.cleaned_data.get(upper)
                if lower_value is not None and upper_value is not None and lower_value > upper_value:
                    self.add_error(upper, ValidationError(bound_ordering_msg, code='bound_ordering'))
            return self.cleaned_data

        cls.clean = clean
        return cls

    return inner


class AmountPattern(enum.Enum):
    not_integral = _('Not a whole number')
    not_multiple_5 = _('Not a multiple of £5')
    not_multiple_10 = _('Not a multiple of £10')
    gte_100 = _('£100 or more')
    exact = _('Exact amount')
    pence = _('Exact number of pence')

    @classmethod
    def get_choices(cls):
        """
        Returns list of choices to be used in forms. It also includes a blank option.
        """
        return [
            ('', _('Any amount')),
            *[
                (choice.name, choice.value)
                for choice in cls
            ],
        ]


class SecurityForm(GARequestErrorReportingMixin, forms.Form):
    """
    Base form for security searches, always uses initial values as defaults
    """
    page = forms.IntegerField(min_value=1, initial=1)
    page_size = 20
    timeout = 60

    exclusive_date_params = []
    exclude_private_estate = False

    filtered_description_template = NotImplemented
    unfiltered_description_template = NotImplemented
    unlisted_description = ''
    description_templates = ()
    description_capitalisation = {}
    default_prison_preposition = 'to'

    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        if self.is_bound:
            for name, field in self.fields.items():
                if name in self.data:
                    continue
                if name in self.initial:
                    self.data[name] = self.initial[name]
                elif field.initial is not None:
                    self.data[name] = field.initial
        self.request = request
        self.total_count = 0
        self.page_count = 0
        self.existing_search = None

        if 'prison' in self.fields:
            self.prison_list = PrisonList(self.session, exclude_private_estate=self.exclude_private_estate)
            self['prison'].field.choices = self.prison_list.prison_choices

            if 'prison' in self.data and hasattr(self.data, 'getlist'):
                selected_prisons = itertools.chain.from_iterable(
                    selection.split(',')
                    for selection in self.data.getlist('prison')
                )
                selected_prisons = sorted(set(filter(None, selected_prisons)))
                self.data.setlist('prison', selected_prisons)

            if 'prison_region' in self.fields:
                self['prison_region'].field.choices = [
                    ('', _('All regions')),
                    *self.prison_list.region_choices,
                ]
            if 'prison_population' in self.fields:
                self['prison_population'].field.choices = [
                    ('', _('All types')),  # blank option
                    *self.prison_list.population_choices,
                ]

            if 'prison_category' in self.fields:
                self['prison_category'].field.choices = [
                    ('', _('All categories')),  # blank option
                    *self.prison_list.category_choices,
                ]

    @cached_property
    def session(self):
        return get_api_session(self.request)

    def get_object_list_endpoint_path(self):
        raise NotImplementedError

    def get_query_data(self, allow_parameter_manipulation=True):
        """
        Serialises the form into a dictionary stripping empty and pagination fields.
        NB: Forms can sometimes manipulate parameters so this is not always reversible.
        :param allow_parameter_manipulation: turn off to make serialisation reversible
        :return: collections.OrderedDict
        """
        data = collections.OrderedDict()
        for field in self:
            if field.name == 'page':
                continue
            value = self.cleaned_data.get(field.name)
            if value in [None, '', []]:
                continue
            data[field.name] = value
        return data

    def get_api_request_params(self):
        filters = self.get_query_data()
        for param in filters:
            if param in self.exclusive_date_params:
                filters[param] += datetime.timedelta(days=1)
        return filters

    def get_api_request_page_params(self):
        page = self.cleaned_data.get('page')
        if not page:
            return None
        filters = self.get_api_request_params()
        filters['offset'] = (page - 1) * self.page_size
        filters['limit'] = self.page_size
        return filters

    def get_object_list(self):
        """
        Gets the security object list: senders, prisoners or credits
        :return: list
        """
        filters = self.get_api_request_page_params()
        if filters is None:
            return []
        try:
            data = self.session.get(
                self.get_object_list_endpoint_path(),
                params=filters,
                timeout=self.timeout,
            ).json()
        except RequestException:
            self.add_error(None, _('This service is currently unavailable'))
            return []
        count = data.get('count', 0)
        self.total_count = count
        self.page_count = int(ceil(count / self.page_size))
        return data.get('results', [])

    def get_complete_object_list(self):
        filters = self.get_api_request_params()
        return convert_date_fields(retrieve_all_pages_for_path(
            self.session, self.get_object_list_endpoint_path(), **filters)
        )

    def build_query_string(self, **extra_query_data):
        query_data = self.get_query_data(allow_parameter_manipulation=False)
        query_data.update(extra_query_data)
        return urlencode(query_data, doseq=True)

    @cached_property
    def query_string(self):
        return self.build_query_string()

    @property
    def query_string_with_page(self):
        return f"page={self.cleaned_data['page']}&{self.query_string}"

    @property
    def query_string_without_ordering(self):
        query_data = self.get_query_data(allow_parameter_manipulation=False)
        query_data.pop('ordering', None)
        return urlencode(query_data, doseq=True)

    def _get_value_text(self, bf, f, v):
        if isinstance(f, forms.ChoiceField):
            v = dict(f.choices).get(v)
            if not v:
                return None
            v = str(v)
            capitalisation = self.description_capitalisation.get(bf.name)
            if capitalisation == 'preserve':
                return v
            if capitalisation == 'lowerfirst':
                return v[0].lower() + v[1:]
            return v.lower()
        if isinstance(f, forms.DateField) and v is not None:
            return date_format(v, 'j M Y')
        if isinstance(f, forms.IntegerField) and v is not None:
            return str(v)
        return v or None

    def _describe_field(self, bf):
        f = bf.field
        v = self.cleaned_data.get(bf.name) or f.initial
        if isinstance(v, list):
            return ', '.join(filter(None, (self._get_value_text(bf, f, i) for i in v)))
        return self._get_value_text(bf, f, v)

    @property
    def search_description(self):
        with override_locale(settings.LANGUAGE_CODE):
            description_kwargs = {
                'ordering_description': self._describe_field(self['ordering']),
            }

            filters = {}
            for bound_field in self:
                if bound_field.name in ('page', 'ordering'):
                    continue
                description_override = 'describe_field_%s' % bound_field.name
                if hasattr(self, description_override):
                    value = getattr(self, description_override)()
                else:
                    value = self._describe_field(bound_field)
                if value is None:
                    continue
                filters[bound_field.name] = format_html('<strong>{}</strong>', value)
            if any(field in filters for field in ('prisoner_number', 'prisoner_name')):
                filters['prison_preposition'] = 'in'
            else:
                filters['prison_preposition'] = self.default_prison_preposition

            descriptions = []
            for template_group in self.description_templates:
                for filter_template in template_group:
                    try:
                        descriptions.append(format_html(filter_template, **filters))
                        break
                    except KeyError:
                        continue

            if descriptions:
                description_template = self.filtered_description_template
                if len(descriptions) > 1:
                    all_but_last = format_html_join(', ', '{}', ((d,) for d in descriptions[:-1]))
                    filter_description = format_html('{0} and {1}', all_but_last, descriptions[-1])
                else:
                    filter_description = descriptions[0]
                description_kwargs['filter_description'] = filter_description
                has_filters = True
            else:
                description_template = self.unfiltered_description_template
                has_filters = False

            return {
                'has_filters': has_filters,
                'description': format_html(
                    description_template + ' {unlisted}',
                    unlisted=self.unlisted_description,
                    **description_kwargs,
                    **self.get_extra_search_description_template_kwargs(),
                ),
            }

    def get_extra_search_description_template_kwargs(self):
        return {}

    def describe_field_prison(self):
        prisons = self.cleaned_data.get('prison')
        if not prisons:
            return
        choices = dict(self.prison_list.prison_choices)
        return ', '.join(sorted(filter(None, map(lambda prison: choices.get(prison), prisons))))


class SecurityDetailForm(SecurityForm):
    def __init__(self, object_id, **kwargs):
        super().__init__(**kwargs)
        self.object_id = object_id

    def get_object_list_endpoint_path(self):
        return urljoin(self.get_object_endpoint_path(), 'credits/')

    def get_object_endpoint_path(self):
        raise NotImplementedError

    def get_object_list(self):
        return convert_date_fields(super().get_object_list())

    def get_object(self):
        """
        Gets the security detail object, a sender or prisoner profile
        :return: dict or None if not found
        """
        try:
            return self.session.get(self.get_object_endpoint_path()).json()
        except HttpNotFoundError:
            self.add_error(None, _('Not found'))
            return None
        except RequestException:
            self.add_error(None, _('This service is currently unavailable'))
            return {}

    def check_and_update_saved_searches(self, page_title):
        site_url = urlparse(self.request.path).path
        self.existing_search = get_existing_search(self.session, site_url)
        if self.existing_search:
            update_result_count(
                self.session, self.existing_search['id'], self.total_count
            )
        if self.request.GET.get('pin') and not self.existing_search:
            endpoint_path = self.get_object_list_endpoint_path()
            self.existing_search = save_search(
                self.session, page_title, endpoint_path, site_url,
                filters=self.get_api_request_params(), last_result_count=self.total_count
            )
            self.session.post(
                '{}monitor/'.format(self.get_object_endpoint_path())
            )
        elif self.request.GET.get('unpin') and self.existing_search:
            delete_search(self.session, self.existing_search['id'])
            self.session.post(
                '{}unmonitor/'.format(self.get_object_endpoint_path())
            )
            self.existing_search = None
