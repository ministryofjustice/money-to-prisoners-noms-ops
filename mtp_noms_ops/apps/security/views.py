import base64
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.utils.dateformat import format as date_format
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from mtp_common.nomis import get_photograph_data
from requests.exceptions import RequestException

from security.export import CreditCsvResponse
from security.forms import (
    SendersForm, SendersDetailForm, PrisonersForm, PrisonersDetailForm, CreditsForm,
    ReviewCreditsForm,
)
from security.tasks import email_credit_csv
from security.utils import NameSet

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
    export_view = False
    export_redirect_view = None

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
        if self.export_view:
            attachment_name = 'exported-%s.csv' % date_format(timezone.now(), 'Y-m-d')
            if self.export_view == 'async':
                email_credit_csv(
                    user=self.request.user,
                    session=self.request.session,
                    endpoint_path=form.get_object_list_endpoint_path(),
                    filters=form.get_query_data(),
                    attachment_name=attachment_name,
                )
                messages.info(
                    self.request,
                    _('The spreadsheet will be emailed to you at %(email)s') % {'email': self.request.user.email}
                )
                return self.get_export_redirect(form)
            return CreditCsvResponse(form.get_complete_object_list(), attachment_name=attachment_name)

        context = self.get_context_data(form=form)
        object_list = form.cleaned_data['object_list']
        form.check_and_update_saved_searches(self.title)
        if self.redirect_on_single and len(object_list) == 1 and hasattr(self, 'url_for_single_result'):
            return redirect(self.url_for_single_result(object_list[0]))
        context[self.object_list_context_key] = object_list
        return render(self.request, self.template_name, context)

    def form_invalid(self, form):
        if self.export_view:
            return self.get_export_redirect(form)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['breadcrumbs'] = [
            {'name': _('Home'), 'url': reverse('dashboard')},
            {'name': self.title}
        ]
        return context_data

    def get_export_redirect(self, form):
        return redirect('%s?%s' % (reverse(self.export_redirect_view, kwargs=self.kwargs), form.query_string))

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
    title = _('Payment sources')
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
            _('%(count)d credits have been marked as checked by security') % {'count': count}
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
                response = HttpResponse(
                    base64.b64decode(b64data), content_type='image/jpeg'
                )
                patch_cache_control(response, private=True, max_age=2592000)
                return response
        except RequestException:
            logger.warning('Could not load image for %s' % prisoner_number)
    if request.GET.get('ratio') == '2x':
        return HttpResponseRedirect(static('images/placeholder-image@2x.png'))
    else:
        return HttpResponseRedirect(static('images/placeholder-image.png'))
