from math import ceil

from django.contrib import messages
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from mtp_common.auth.api_client import get_connection

from security.export import export_as_csv
from security.forms import (
    SendersForm, PrisonersForm, CreditsForm, ReviewCreditsForm
)
from security.utils import NameSet, EmailSet


class SecurityView(FormView):
    """
    Base view for retrieving security-related searches
    Allows form submission via GET (using page parameter as the flag)
    """
    title = NotImplemented
    template_name = NotImplemented
    form_template_name = NotImplemented
    object_list_context_key = NotImplemented

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.redirect_on_single = False

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs['request'] = self.request
        request_data = self.request.GET.dict()
        if 'redirect-on-single' in request_data:
            self.redirect_on_single = True
        if 'page' not in request_data:
            request_data['page'] = '1'
        form_kwargs['data'] = request_data
        return form_kwargs

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        object_list = form.get_object_list()
        if self.redirect_on_single and len(object_list) == 1 and hasattr(self, 'url_for_single_result'):
            return redirect(self.url_for_single_result(object_list[0]))
        context[self.object_list_context_key] = object_list
        return render(self.request, self.template_name, context)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['breadcrumbs'] = [
            {'name': _('Home'), 'url': reverse('dashboard')},
            {'name': self.title}
        ]
        return context_data

    get = FormView.post


class SecurityDetailView(TemplateView):
    title = NotImplemented
    list_title = NotImplemented
    list_url = NotImplemented
    template_name = NotImplemented
    id_kwarg_name = NotImplemented
    object_name = NotImplemented
    page_size = 20

    def get_api_endpoint(self, client):
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = get_connection(self.request)
        endpoint = self.get_api_endpoint(client)(self.kwargs[self.id_kwarg_name])

        detail_object = endpoint.get()
        self.title = self.get_title_for_object(detail_object)
        list_url = self.request.build_absolute_uri(str(self.list_url))
        referrer_url = self.request.META.get('HTTP_REFERER', '-')
        if referrer_url.startswith(list_url):
            list_url = referrer_url
        try:
            page = int(self.request.GET.get('page', 1))
            if page < 1:
                raise ValueError
        except ValueError:
            page = 1
        offset = (page - 1) * self.page_size
        data = endpoint.credits.get(offset=offset, limit=self.page_size)
        count = data['count']
        context[self.object_name] = detail_object
        context['page'] = page
        context['page_count'] = int(ceil(count / self.page_size))
        context['credits'] = data.get('results', [])
        context['breadcrumbs'] = [
            {'name': _('Home'), 'url': reverse('dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': self.title}
        ]
        return context

    def get_title_for_object(self, detail_object):
        raise NotImplementedError


class CreditListView(SecurityView):
    """
    Credit search view
    """
    title = _('Credits')
    form_template_name = 'security/forms/credits.html'
    template_name = 'security/credits.html'
    form_class = CreditsForm
    object_list_context_key = 'credits'


class SenderListView(SecurityView):
    """
    Sender search view
    """
    title = _('Senders')
    form_template_name = 'security/forms/senders.html'
    template_name = 'security/senders.html'
    form_class = SendersForm
    object_list_context_key = 'senders'

    def url_for_single_result(self, sender):
        return reverse('security:sender_detail', kwargs={'sender_id': sender['id']})


class SenderDetailView(SecurityDetailView):
    """
    Sender profile view
    """
    list_title = SenderListView.title
    list_url = reverse_lazy('security:sender_list')
    template_name = 'security/senders-detail.html'
    id_kwarg_name = 'sender_id'
    object_name = 'sender'

    def get_api_endpoint(self, client):
        return client.senders

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        sender = context_data['sender']

        all_cardholder_names = list(details['sender_name']
                                    for details in sender.get('bank_transfer_details', ()))
        all_cardholder_names.extend(cardholder_name
                                    for details in sender.get('debit_card_details', ())
                                    for cardholder_name in details['cardholder_names'])
        context_data['all_cardholder_names'] = all_cardholder_names
        other_cardholder_names = NameSet(strip_titles=True)
        other_cardholder_names.extend(all_cardholder_names)
        if other_cardholder_names:
            other_cardholder_names.pop_first()
        context_data['other_cardholder_names'] = other_cardholder_names

        sender_emails = EmailSet(sender_email
                                 for details in sender.get('debit_card_details', ())
                                 for sender_email in details['sender_emails'])
        context_data['sender_emails'] = sender_emails

        return context_data

    def get_title_for_object(self, detail_object):
        try:
            return detail_object['bank_transfer_details'][0]['sender_name']
        except (KeyError, IndexError):
            pass
        try:
            return detail_object['debit_card_details'][0]['cardholder_names'][0]
        except (KeyError, IndexError):
            pass
        return '—'


class PrisonerListView(SecurityView):
    """
    Prisoner search view
    """
    title = _('Prisoners')
    form_template_name = 'security/forms/prisoners.html'
    template_name = 'security/prisoners.html'
    form_class = PrisonersForm
    object_list_context_key = 'prisoners'

    def url_for_single_result(self, prisoner):
        return reverse('security:prisoner_detail', kwargs={'prisoner_id': prisoner['id']})


class PrisonerDetailView(SecurityDetailView):
    """
    Prisoner profile view
    """
    list_title = PrisonerListView.title
    list_url = reverse_lazy('security:prisoner_list')
    template_name = 'security/prisoners-detail.html'
    id_kwarg_name = 'prisoner_id'
    object_name = 'prisoner'

    def get_api_endpoint(self, client):
        return client.prisoners

    def get_title_for_object(self, detail_object):
        title = ' '.join(detail_object.get(key) for key in ('prisoner_number', 'prisoner_name'))
        return title.strip() or '—'


class CreditExportView(SecurityView):
    form_class = CreditsForm

    def form_valid(self, form):
        data = form.get_complete_object_list()
        csvdata = export_as_csv(data)
        response = HttpResponse(csvdata, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="export.csv"'
        return response

    def form_invalid(self, form):
        return redirect('?'.join(
            filter(lambda x: x, [reverse('security:credit_list'), form.query_string])
        ))

    def get(self, request, *args, **kwargs):
        if 'page' in self.request.GET:
            return self.post(request, *args, **kwargs)
        return redirect('?'.join(
            filter(lambda x: x, [reverse('security:credit_list'), request.GET.urlencode()])
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
