from math import ceil

from django.contrib import messages
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import QueryDict, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from mtp_common.auth.api_client import get_connection

from security.export import export_as_csv
from security.forms import (
    SenderGroupedForm, PrisonerGroupedForm, CreditsForm, ReviewCreditsForm
)


def dashboard_view(request):
    return render(request, 'security/dashboard.html')


class SecurityView(FormView):
    """
    Base view for retrieving security-related searches
    Allows form submission via GET (using page parameter as the flag)
    """
    title = NotImplemented
    help_template_name = NotImplemented
    template_name = 'security/search.html'
    form_template_name = 'security/form.html'
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

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['breadcrumbs'] = [
            {'name': _('Search'), 'url': reverse('security:dashboard')},
            {'name': self.title}
        ]
        return context_data

    def get(self, request, *args, **kwargs):
        if 'page' in self.request.GET:
            return self.post(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)


class GroupedSecurityView(SecurityView):
    listing_credits = False
    credits_view = NotImplemented
    credits_template_name = NotImplemented
    credits_ajax_template_name = NotImplemented
    page_size = 20

    sender_keys = ('sender_name', 'sender_sort_code', 'sender_account_number', 'sender_roll_number')
    prisoner_keys = ('prisoner_name', 'prisoner_number')

    blank_keys = ()

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
        ajax = query_string.get('ajax', False)
        query_string = query_string.urlencode()

        filters.pop('prisoner_name', None)  # this should not be used to identify prisoners
        filters.pop('return_to', None)  # this is for navigation not filtering
        filters.update(self.form_class.extra_filters)

        # convert empty filters into 'isblank' filters for special keys
        for blank_key in self.blank_keys:
            if filters.get(blank_key, None) == '':
                del filters[blank_key]
                filters['%s__isblank' % blank_key] = True

        offset = (page - 1) * self.page_size
        data = client.credits.get(offset=offset, limit=self.page_size, **filters)
        count = data['count']
        page_count = int(ceil(count / self.page_size))
        context = {
            'view': self,
            'page': page,
            'page_count': page_count,
            'query_string': query_string,
            'credits': data.get('results', []),
        }
        template_name = self.credits_ajax_template_name if ajax else self.credits_template_name
        return render(request, template_name, context)

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
    title = _('From one sender to many prisoners')
    help_template_name = 'security/sender-grouped-help.html'
    form_template_name = 'security/sender-grouped-form.html'
    results_template_name = 'security/sender-grouped.html'
    credits_template_name = 'security/sender-grouped-credits.html'
    credits_ajax_template_name = 'security/prisoner-grouped-credits-ajax.html'
    credits_view = 'security:sender_grouped_credits'
    form_class = SenderGroupedForm
    blank_keys = ('sender_name', 'sender_sort_code', 'sender_account_number', 'sender_roll_number')

    def get_credits_view(self, request):
        if not all(key in request.GET for key in self.sender_keys):
            return redirect('security:dashboard')
        return super().get_credits_view(request)

    def get_credit_row_query_dict(self, group, row):
        query_dict = {
            key: value
            for key, value in group.items()
            if key in self.sender_keys
        }
        if not row['prison_name']:
            query_dict['prison__isnull'] = 'True'
        else:
            query_dict.update({
                key: value
                for key, value in row.items()
                if value and key in self.prisoner_keys
            })
            prison = row.get('prison_id')
            if prison:
                query_dict['prison'] = prison
        return query_dict


class PrisonerGroupedView(GroupedSecurityView):
    """
    Show list of prisoners who received from multiple senders
    """
    title = _('To one prisoner from many senders')
    help_template_name = 'security/prisoner-grouped-help.html'
    form_template_name = 'security/prisoner-grouped-form.html'
    results_template_name = 'security/prisoner-grouped.html'
    credits_template_name = 'security/prisoner-grouped-credits.html'
    credits_ajax_template_name = 'security/prisoner-grouped-credits-ajax.html'
    credits_view = 'security:prisoner_grouped_credits'
    form_class = PrisonerGroupedForm

    def get_credits_view(self, request):
        if not all(key in request.GET for key in self.prisoner_keys):
            return redirect('security:dashboard')
        return super().get_credits_view(request)

    def get_credit_row_query_dict(self, group, row):
        query_dict = {
            key: value
            for key, value in group.items()
            if key in self.prisoner_keys
        }
        query_dict.update({
            key: value
            for key, value in row.items()
            if value and key in self.sender_keys
        })
        return query_dict


class CreditsView(SecurityView):
    """
    Open-ended search view
    """
    title = _('All credits')
    help_template_name = 'security/credits-help.html'
    form_template_name = 'security/credits-form.html'
    results_template_name = 'security/credits.html'
    form_class = CreditsForm

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        context['credits'] = form.get_object_list()
        return render(self.request, self.results_template_name, context)


class CreditsExportView(SecurityView):
    form_class = CreditsForm

    def form_valid(self, form):
        data = form.get_complete_object_list()
        csvdata = export_as_csv(data)
        response = HttpResponse(csvdata, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="export.csv"'
        return response

    def form_invalid(self, form):
        return redirect('?'.join(
            filter(lambda x: x, [reverse('security:credits'), form.query_string])
        ))

    def get(self, request, *args, **kwargs):
        if 'page' in self.request.GET:
            return self.post(request, *args, **kwargs)
        return redirect('?'.join(
            filter(lambda x: x, [reverse('security:credits'), request.GET.urlencode()])
        ))


class ReviewCreditsView(FormView):
    title = _('New credits check')
    form_class = ReviewCreditsForm
    template_name = 'security/review.html'
    success_url = reverse_lazy('security:review_credits')

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs['request'] = self.request
        return form_kwargs

    def form_valid(self, form):
        count = form.review()
        messages.add_message(
            self.request, messages.INFO,
            _('{count} credits have been marked as checked by security').format(count=count)
        )
        return super().form_valid(form=form)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['credits'] = context_data['form'].credits
        return context_data
