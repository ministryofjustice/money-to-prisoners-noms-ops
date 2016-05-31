from math import ceil

from django.http import QueryDict
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from mtp_common.auth.api_client import get_connection

from mtp_noms_ops.view_utils import make_page_range
from security.forms import SenderGroupedForm, PrisonerGroupedForm, CreditsForm


def dashboard_view(request):
    return render(request, 'security/dashboard.html')


class SecurityView(FormView):
    """
    Base view for retrieving security-related searches
    Allows form submission via GET (using page parameter as the flag)
    """
    title = NotImplemented
    intro_text = NotImplemented
    template_name = 'security/search.html'
    results_template_name = NotImplemented

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs['request'] = self.request
        if 'page' in self.request.GET:
            form_kwargs['data'] = self.request.GET
        else:
            form_kwargs['initial'].update(self.request.GET.dict())
        return form_kwargs

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        return render(self.request, self.results_template_name, context)

    def get(self, request, *args, **kwargs):
        if 'page' in self.request.GET:
            return self.post(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)


class GroupedSecurityView(SecurityView):
    listing_credits = False
    credits_view = NotImplemented
    page_size = 20

    sender_identifiers = ('sender_name', 'sender_sort_code', 'sender_account_number', 'sender_roll_number')
    prisoner_identifiers = ('prisoner_number',)

    def get(self, request, *args, **kwargs):
        if not self.listing_credits:
            return super().get(request, *args, **kwargs)
        return self.get_credits_view(request)

    def get_credits_view(self, request):
        client = get_connection(request)
        filters = request.GET.dict()
        try:
            page = int(filters.pop('page', 1))
            if page < 1:
                raise ValueError
        except (KeyError, ValueError):
            page = 1
        query_string = QueryDict(mutable=True)
        for key, value in filters.items():
            if value:
                query_string[key] = value
        offset = (page - 1) * self.page_size
        data = client.credits.get(offset=offset, limit=self.page_size, **filters)
        count = data['count']
        page_count = int(ceil(count / self.page_size))
        context = {
            'view': self,
            'page': page,
            'page_count': page_count,
            'page_range': make_page_range(page, page_count),
            'query_string': query_string.urlencode(),
            'credits': data.get('results', []),
        }
        return render(request, 'security/grouped-results-details.html', context)

    def get_credits_row_query_string(self, form, group, row):
        query_string = QueryDict(form.query_string, mutable=True)
        for key, value in self.get_credit_row_query_dict(group, row).items():
            query_string[key] = value
        return query_string.urlencode()

    def get_credit_row_query_dict(self, group, row):
        raise NotImplementedError


class SenderGroupedView(GroupedSecurityView):
    """
    Show list of senders who sent to multiple prisoners
    """
    title = _('Search by sender')
    intro_text = _('Use this search to find payments sent to multiple prisoners')
    results_template_name = 'security/sender-grouped.html'
    credits_view = 'security:sender_grouped_credits'
    form_class = SenderGroupedForm

    def get_credit_row_query_dict(self, group, row):
        query_dict = {
            key: value
            for key, value in group.items()
            if value and key in self.sender_identifiers
        }
        if not row['prisoner_number']:
            query_dict['status'] = 'refundable'  # TODO
        else:
            query_dict.update({
                key: value
                for key, value in row.items()
                if value and key in self.prisoner_identifiers
            })
        return query_dict


class PrisonerGroupedView(GroupedSecurityView):
    """
    Show list of prisoners who received from multiple senders
    """
    title = _('Search by prisoner')
    intro_text = _('Use this search to find payments sent to prisoners from multiple senders')
    results_template_name = 'security/prisoner-grouped.html'
    credits_view = 'security:prisoner_grouped_credits'
    form_class = PrisonerGroupedForm

    def get_credit_row_query_dict(self, group, row):
        query_dict = {
            key: value
            for key, value in group.items()
            if value and key in self.prisoner_identifiers
        }
        query_dict.update({
            key: value
            for key, value in row.items()
            if value and key in self.sender_identifiers
        })
        return query_dict


class CreditsView(SecurityView):
    """
    Open-ended search view
    """
    title = _('Search by details')
    intro_text = _('Use this search to list payments based on various filters')
    results_template_name = 'security/credits-results.html'
    form_class = CreditsForm

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        context['credits'] = form.get_object_list()
        return render(self.request, self.results_template_name, context)
