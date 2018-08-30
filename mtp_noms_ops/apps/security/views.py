import base64
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.utils.cache import patch_cache_control
from django.utils.http import is_safe_url
from django.utils.translation import gettext, gettext_lazy as _
from django.views.generic import FormView, TemplateView
from mtp_common.auth import USER_DATA_SESSION_KEY
from mtp_common.auth.api_client import get_api_session
from mtp_common.nomis import get_photograph_data, get_location
from requests.exceptions import RequestException

from security import hmpps_employee_flag, not_hmpps_employee_flag
from security.forms import (
    SendersForm, SendersDetailForm,
    PrisonersForm, PrisonersDetailForm, PrisonersDisbursementDetailForm,
    CreditsForm,
    DisbursementsForm,
    ReviewCreditsForm,
    HMPPSEmployeeForm,
)
from security.templatetags.security import currency as format_currency
from security.utils import NameSet, nomis_api_available, parse_date_fields
from security.views_base import SimpleSecurityDetailView, SecurityView, SecurityDetailView

logger = logging.getLogger('mtp')


class CreditListView(SecurityView):
    """
    Credit search view
    """
    title = _('Credits')
    form_template_name = 'security/forms/credits.html'
    template_name = 'security/credits.html'
    form_class = CreditsForm
    object_list_context_key = 'credits'


class CreditDetailView(SimpleSecurityDetailView):
    """
    Credit detail view
    """
    title = _('Credit')
    template_name = 'security/credit.html'
    object_context_key = 'credit'
    list_title = _('Credits')
    list_url = reverse_lazy('security:credit_list')

    def get_object_request_params(self):
        return {
            'url': '/credits/',
            'params': {'pk': self.kwargs['credit_id']}
        }

    def get_object(self):
        response = super().get_object()
        if not response:
            return {}
        if response['count'] != 1:
            raise Http404('credit not found')
        credit = parse_date_fields(response['results'])[0]
        return credit

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        if self.object:
            self.title = ' '.join((format_currency(self.object['amount']) or '', gettext('credit')))
        return context_data


class DisbursementListView(SecurityView):
    """
    Disbursement search view
    """
    title = _('Disbursements')
    form_template_name = 'security/forms/disbursements.html'
    template_name = 'security/disbursements.html'
    form_class = DisbursementsForm
    object_list_context_key = 'disbursements'

    def dispatch(self, request, *args, **kwargs):
        if not request.disbursements_available:
            raise Http404('Disbursements not available to current user')
        return super().dispatch(request, *args, **kwargs)


class DisbursementDetailView(SimpleSecurityDetailView):
    """
    Disbursement detail view
    """
    title = _('Disbursement')
    template_name = 'security/disbursement.html'
    object_context_key = 'disbursement'
    list_title = _('Disbursements')
    list_url = reverse_lazy('security:disbursement_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.disbursements_available:
            raise Http404('Disbursements not available to current user')
        return super().dispatch(request, *args, **kwargs)

    def get_object_request_params(self):
        return {
            'url': '/disbursements/%s/' % self.kwargs['disbursement_id']
        }

    def get_object(self):
        disbursement = super().get_object()
        if disbursement:
            disbursement = parse_date_fields([disbursement])[0]
            self.format_log_set(disbursement)
            disbursement['recipient_name'] = ('%s %s' % (disbursement['recipient_first_name'],
                                                         disbursement['recipient_last_name'])).strip()
        return disbursement

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        if self.object:
            self.title = ' '.join((format_currency(self.object['amount']) or '', gettext('disbursement')))
        return context_data

    def format_log_set(self, disbursement):
        def format_staff_name(log_item):
            username = log_item['user']['username'] or _('Unknown user')
            log_item['staff_name'] = ' '.join(filter(None, (log_item['user']['first_name'],
                                                            log_item['user']['last_name']))) or username
            return log_item

        disbursement['log_set'] = sorted(
            map(format_staff_name, parse_date_fields(disbursement.get('log_set', []))),
            key=lambda log_item: log_item['created']
        )


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
    Prisoner profile view showing credit list
    """
    list_title = PrisonerListView.title
    list_url = reverse_lazy('security:prisoner_list')
    template_name = 'security/prisoner.html'
    form_class = PrisonersDetailForm
    id_kwarg_name = 'prisoner_id'
    object_context_key = 'prisoner'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        prisoner = context_data.get('prisoner', {})
        if prisoner:
            context_data['provided_names'] = NameSet(
                prisoner.get('provided_names', ()), strip_titles=True
            )
            if self.request.disbursements_available:
                context_data['disbursement_count'] = self.get_disbursement_count(
                    context_data['form'].session, prisoner['prisoner_number']
                )
        return context_data

    def get_title_for_object(self, detail_object):
        title = ' '.join(detail_object.get(key, '') for key in ('prisoner_number', 'prisoner_name'))
        return title.strip() or _('Unknown prisoner')

    def get_disbursement_count(self, session, prisoner_number):
        try:
            response = session.get('/disbursements/', params={
                'prisoner_number': prisoner_number,
                # exclude rejected/cancelled disbursements
                'resolution': ['pending', 'preconfirmed', 'confirmed', 'sent'],
                'limit': 1,
            }).json()
            return response['count']
        except (RequestException, ValueError, KeyError):
            return None


class PrisonerDisbursementDetailView(PrisonerDetailView):
    """
    Prisoner profile view showing disbursement list
    """
    template_name = 'security/prisoner-disbursements.html'
    form_class = PrisonersDisbursementDetailForm
    object_list_context_key = 'disbursements'

    def dispatch(self, request, *args, **kwargs):
        if not request.disbursements_available:
            raise Http404('Disbursements not available to current user')
        return super().dispatch(request, *args, **kwargs)


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
    if nomis_api_available(request) and prisoner_number:
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


def prisoner_nomis_info_view(request, prisoner_number):
    response_data = {}
    if nomis_api_available(request) and prisoner_number:
        try:
            location = get_location(prisoner_number)
            if 'housing_location' in location:
                housing = location['housing_location']
                if housing['levels']:
                    # effectively drops prison code prefix from description
                    response_data['housing_location'] = '-'.join(
                        level['value'] for level in housing['levels']
                    )
                else:
                    response_data['housing_location'] = housing['description']
        except RequestException:
            logger.warning('Could not load location for %s' % prisoner_number)
    response = JsonResponse(response_data)
    patch_cache_control(response, private=True, max_age=3600)
    return response


class HMPPSEmployeeView(FormView):
    title = _('Confirm your eligibility')
    template_name = 'hmpps-employee.html'
    form_class = HMPPSEmployeeForm
    success_url = reverse_lazy(settings.LOGIN_REDIRECT_URL)
    not_employee_url = reverse_lazy('security:not_hmpps_employee')

    def dispatch(self, request, *args, **kwargs):
        if not request.can_access_security:
            return redirect(self.success_url)
        flags = request.user.user_data.get('flags') or []
        if hmpps_employee_flag in flags:
            return redirect(self.success_url)
        if not_hmpps_employee_flag in flags:
            return redirect(self.not_employee_url)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial['next'] = self.request.META.get('HTTP_REFERER', '')
        return initial

    def save_user(self, flag, deactivate=False):
        request = self.request
        api_session = get_api_session(request)
        api_session.put('/users/%s/flags/%s/' % (request.user.username, flag), json={})
        if deactivate:
            api_session.delete('/users/%s/' % request.user.username)
        else:
            flags = set(request.user.user_data.get('flags') or [])
            flags.add(flag)
            flags = list(flags)
            request.user.user_data['flags'] = flags
            request.session[USER_DATA_SESSION_KEY] = request.user.user_data

    def form_valid(self, form):
        confirmation = form.cleaned_data['confirmation']
        if confirmation == 'yes':
            self.save_user(hmpps_employee_flag)
            success_url = form.cleaned_data['next']
            if success_url and is_safe_url(success_url, host=self.request.get_host()):
                self.success_url = success_url
            return super().form_valid(form)
        else:
            self.save_user(not_hmpps_employee_flag, True)
            self.request.session.flush()
            return redirect(self.not_employee_url)


class NotHMPPSEmployeeView(TemplateView):
    title = _('You can’t use this tool')
    template_name = 'not-hmpps-employee.html'

    def dispatch(self, request, *args, **kwargs):
        flags = request.user.user_data.get('flags') or []
        if request.user.is_authenticated and not_hmpps_employee_flag not in flags:
            return redirect(reverse(settings.LOGIN_REDIRECT_URL))
        return super().dispatch(request, *args, **kwargs)
