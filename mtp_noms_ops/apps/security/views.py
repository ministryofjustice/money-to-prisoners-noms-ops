import base64
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from mtp_common.nomis import get_photograph_data
from requests.exceptions import RequestException

from security.export import export_as_csv
from security.forms import (
    SendersForm, SendersDetailForm, PrisonersForm, PrisonersDetailForm, CreditsForm,
    ReviewCreditsForm,
)
from security.utils import NameSet, EmailSet

logger = logging.getLogger('mtp')


class SecurityView(FormView):
    """
    Base view for retrieving security-related searches
    Allows form submission via GET
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
        object_list = form.cleaned_data['object_list']
        form.check_and_update_saved_searches(self.title)
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


class SecurityDetailView(SecurityView):
    """
    Base view for presenting a profile with associated credits
    Allows form submission via GET
    """
    list_title = NotImplemented
    list_url = NotImplemented
    id_kwarg_name = NotImplemented
    object_list_context_key = 'credits'
    object_context_key = NotImplemented

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs['object_id'] = self.kwargs[self.id_kwarg_name]
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        detail_object = context_data['form'].cleaned_data.get('object')
        if detail_object is None:
            raise Http404('Detail object not found')
        self.title = self.get_title_for_object(detail_object)
        list_url = self.request.build_absolute_uri(str(self.list_url))
        referrer_url = self.request.META.get('HTTP_REFERER', '-')
        if referrer_url.split('?', 1)[0] == list_url:
            list_url = referrer_url
        context_data[self.object_context_key] = detail_object

        context_data['breadcrumbs'] = [
            {'name': _('Home'), 'url': reverse('dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': self.title}
        ]
        return context_data

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
    form_class = SendersDetailForm
    id_kwarg_name = 'sender_id'
    object_context_key = 'sender'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        sender = context_data.get('sender', {})

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
        return _('Unknown sender')


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
    form_class = PrisonersDetailForm
    id_kwarg_name = 'prisoner_id'
    object_context_key = 'prisoner'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        prisoner = context_data.get('prisoner', {})
        context_data['recipient_names'] = NameSet(prisoner.get('recipient_names', ()), strip_titles=True)
        return context_data

    def get_title_for_object(self, detail_object):
        title = ' '.join(detail_object.get(key, '') for key in ('prisoner_number', 'prisoner_name'))
        return title.strip() or _('Unknown prisoner')


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


def prisoner_image_view(request, prisoner_number):
    if settings.NOMIS_API_AVAILABLE and prisoner_number:
        try:
            b64data = get_photograph_data(prisoner_number)
            if b64data:
                return HttpResponse(
                    base64.b64decode(b64data), content_type='image/jpeg'
                )
        except RequestException:
            logger.warning('Could not load image for %s' % prisoner_number)
    if request.GET.get('ratio') == '2x':
        return HttpResponseRedirect(static('images/placeholder-image@2x.png'))
    else:
        return HttpResponseRedirect(static('images/placeholder-image.png'))
