import logging
from functools import lru_cache

from django import forms
from django.forms.widgets import TextInput
from django.contrib import messages
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth.api_client import get_api_session
from requests.exceptions import RequestException

from security.forms.object_base import SecurityForm
from security.utils import convert_date_fields, get_need_attention_date

logger = logging.getLogger('mtp')


class CheckListForm(SecurityForm):
    """
    List of security checks.
    """

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        self.need_attention_date = get_need_attention_date()
        self.need_attention_count = 0
        self.my_list_count = 0

    def get_api_request_params(self):
        """
        Gets pending checks only, for now.
        """
        return dict(
            super().get_api_request_params(),
            **{
                'status': 'pending',
                'credit_resolution': 'initial'
            }
        )

    def get_object_list_endpoint_path(self):
        return '/security/checks/'

    def get_object_list(self):
        """
        Gets objects, converts datetimes found in them and looks up counts of urgent and assigned checks.
        """
        self.need_attention_count = self.session.get(self.get_object_list_endpoint_path(), params=dict(
            self.get_api_request_params(),
            **{
                'started_at__lt': self.need_attention_date.strftime('%Y-%m-%d %H:%M:%S'),
                'offset': 0,
                'limit': 1,
            }
        )).json()['count']
        self.my_list_count = self.session.get(self.get_object_list_endpoint_path(), params=dict(
            self.get_api_request_params(),
            **{
                'assigned_to': self.request.user.pk,
                'offset': 0,
                'limit': 1,
            }
        )).json()['count']

        object_list = convert_date_fields(super().get_object_list(), include_nested=True)
        for check in object_list:
            check['needs_attention'] = check['credit']['started_at'] < self.need_attention_date

        return object_list


class UserCheckListForm(CheckListForm):

    def get_api_request_params(self):
        return dict(
            super().get_api_request_params(),
            assigned_to=self.request.user.pk
        )


class CreditsHistoryListForm(SecurityForm):
    """
    List of security checks.
    """
    CHECKS_STARTED = '2020-01-02T12:00:00'

    ordering = forms.ChoiceField(
        label=_('Order by'),
        required=False,
        initial='-created',
        choices=[
            ('created', _('Date started (oldest to newest)')),
            ('-created', _('Date started (newest to oldest)')),
        ],
    )

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        self.my_list_count = 0

    def get_api_request_params(self):
        """
        Gets all checks where actioned_by is not None.
        """
        params = super().get_api_request_params()
        params['actioned_by'] = True
        params['started_at__gte'] = self.CHECKS_STARTED
        return params

    def get_object_list_endpoint_path(self):
        return '/security/checks/'

    def get_object_list(self):
        """
        Gets objects, converts datetimes found in them.
        """
        object_list = convert_date_fields(super().get_object_list(), include_nested=True)
        self.my_list_count = self.session.get(self.get_object_list_endpoint_path(), params={
            'status': 'pending',
            'credit_resolution': 'initial',
            'assigned_to': self.request.user.pk,
            'offset': 0,
            'limit': 1
        }).json()['count']
        return object_list


class ToggleableTextInput(TextInput):
    """
    Omits element value from being returned when clean called on associated field if disabled

    This serves two purposes. The main one is allow the textinput fields to be toggled without re-rendering the page
    as this causes the problem of having to move the window back to its previous location.

    The other (more minor) useability improvement is that it removes the unintuitive behaviour of the text disappearing
    if the user selects the checkbox that toggles this text field, deselects it and then reselects it again.

    We use the ignore-input class on the field (toggled via javascript) to determine if we should include the value of
    the associated html element in the cleaned_data associated with the field
    """
    def value_from_datadict(self, data, files, name):
        response = super().value_from_datadict(data, files, name)
        if 'ignore-input' in self.attrs.get('class', '').split(' '):
            return ''
        return response


class AcceptOrRejectCheckForm(GARequestErrorReportingMixin, forms.Form):
    """
    CheckForm for accepting or rejecting a check.
    """

    fiu_action = forms.CharField(max_length=10)
    accept_further_details = forms.CharField(
        label=_('Give Further details (Optional)'),
        required=False,
    )
    reject_further_details = forms.CharField(
        label=_('Give Further details (Optional)'),
        required=False,
    )
    fiu_investigation_id = forms.CharField(
        required=False,
        widget=ToggleableTextInput,
        label=_('Associated FIU investigation')
    )
    intelligence_report_id = forms.CharField(
        required=False,
        widget=ToggleableTextInput,
        label=_('Associated Intelligence Report (IR)')
    )
    other_reason = forms.CharField(
        required=False,
        widget=ToggleableTextInput,
        label=_('Other Reason')
    )
    payment_source_paying_multiple_prisoners = forms.BooleanField(
        required=False,
        label=_('Payment source is paying multiple prisoners')
    )
    payment_source_multiple_cards = forms.BooleanField(
        required=False,
        label=_('Payment source is using multiple cards')
    )
    payment_source_linked_other_prisoners = forms.BooleanField(
        required=False,
        label=_('Payment source is linked to other prisoner/s')
    )
    payment_source_known_email = forms.BooleanField(
        required=False,
        label=_('Payment source is using a known email')
    )
    payment_source_unidentified = forms.BooleanField(
        required=False,
        label=_('Payment source is unidentified')
    )
    prisoner_multiple_payments_payment_sources = forms.BooleanField(
        required=False,
        label=_('Prisoner has multiple payments or payment sources')
    )

    error_messages = {
        'missing_reject_reason': _('You must provide a reason for rejecting a credit'),
        'reject_with_accept_details': _('You cannot reject with the Add Further Details box under accept populated'),
        'accept_with_reject_details': _('You cannot accept with the Add Further Details box under reject populated'),
        'accept_with_reject_reason': _('You must untick all rejection fields before accepting a credit'),
    }

    def __init__(self, object_id, request, **kwargs):
        super().__init__(**kwargs)
        self.object_id = object_id
        self.need_attention_date = get_need_attention_date()
        self.request = request
        self.mandatory_rejection_text_fields = (
            'fiu_investigation_id',
            'intelligence_report_id',
            'other_reason',
        )
        self.rejection_checkbox_fields = (
            'payment_source_paying_multiple_prisoners',
            'payment_source_multiple_cards',
            'payment_source_linked_other_prisoners',
            'payment_source_known_email',
            'payment_source_unidentified',
            'prisoner_multiple_payments_payment_sources',
        )
        self.rejection_reason_fields = self.rejection_checkbox_fields + self.mandatory_rejection_text_fields

    @lru_cache()
    def get_object(self):
        """
        Gets the check object
        :return: dict or None if not found
        """
        try:
            obj = self.session.get(self.get_object_endpoint_path()).json()
            convert_dates_obj = convert_date_fields(obj, include_nested=True)
            convert_dates_obj['needs_attention'] = convert_dates_obj['credit']['started_at'] < self.need_attention_date
            return obj
        except RequestException:
            return None

    def get_object_endpoint_path(self):
        return f'/security/checks/{self.object_id}/'

    @cached_property
    def session(self):
        return get_api_session(self.request)

    def is_reject_reason_populated(self):
        return any([
            self.cleaned_data.get(rejection_field)
            for rejection_field in self.rejection_reason_fields
        ])

    def clean(self):
        """
        Makes sure that the check is in the correct state and validate field combination.
        """
        status = self.cleaned_data['fiu_action']

        if not self.errors:  # if already in error => skip
            if self.get_object()['status'] != 'pending':
                raise forms.ValidationError(
                    _('You cannot action this credit as it’s not in pending'),
                )

        if status == 'reject':
            if not self.is_reject_reason_populated():
                self.add_error(
                    None,
                    self.error_messages['missing_reject_reason']
                )
            if self.cleaned_data.get('accept_further_details'):
                self.add_error(
                    'accept_further_details',
                    self.error_messages['reject_with_accept_details']
                )
            self.cleaned_data['further_details'] = self.cleaned_data.pop('reject_further_details')
            del self.cleaned_data['accept_further_details']

        elif status == 'accept':
            if self.is_reject_reason_populated():
                self.add_error(
                    None,
                    self.error_messages['accept_with_reject_reason'],
                )
            if self.cleaned_data.get('reject_further_details'):
                self.add_error(
                    'reject_further_details',
                    self.error_messages['accept_with_reject_details'],
                )
            self.cleaned_data['further_details'] = self.cleaned_data.pop('accept_further_details')
            del self.cleaned_data['reject_further_details']

        return super().clean()

    def get_resolve_endpoint_path(self, fiu_action='accept'):
        return f'/security/checks/{self.object_id}/{fiu_action}/'

    def accept_or_reject(self):
        """
        Accepts or rejects the check via the API.
        :return: True if the API call was successful.
            If not, it returns False and populating the self.errors dict.
        """
        endpoint = self.get_resolve_endpoint_path(fiu_action=self.cleaned_data.pop('fiu_action'))

        try:
            self.session.post(
                endpoint,
                json=self.cleaned_data
            )
            return True
        except RequestException:
            logger.exception(f'Check {self.object_id} could not be actioned')
            self.add_error(None, _('There was an error with your request.'))
            return False


class AssignCheckToUserForm(GARequestErrorReportingMixin, forms.Form):
    assignment = forms.ChoiceField(
        choices=[
            ('assign', _('Assign')),
            ('unassign', _('Unassign')),
        ],
        required=True
    )

    def __init__(self, object_id, request, **kwargs):
        super().__init__(**kwargs)
        self.object_id = object_id
        self.request = request

    @cached_property
    def session(self):
        return get_api_session(self.request)

    def get_endpoint_path(self):
        return f'/security/checks/{self.object_id}/'

    def assign_or_unassign(self):
        endpoint = self.get_endpoint_path()

        if self.cleaned_data.get('assignment') == 'assign':
            user_id = self.request.user.pk
        elif self.cleaned_data.get('assignment') == 'unassign':
            user_id = None

        try:
            self.session.patch(
                endpoint,
                json={
                    'assigned_to': user_id
                }
            )
            return True
        except RequestException as e:
            msg = _('Credit could not be added to your list.')
            if hasattr(e, 'response') and e.response.content:
                try:
                    maybe_json = e.response.json()[0]
                except (ValueError, KeyError):
                    pass
                else:
                    msg = maybe_json
            logger.exception(f'Check {self.object_id} could not be assigned')
            messages.add_message(
                self.request,
                messages.ERROR,
                msg
            )
            return False
