import logging
from functools import lru_cache

from django import forms
from django.contrib import messages
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth.api_client import get_api_session
from requests.exceptions import RequestException

from security.constants import CHECK_DETAIL_FORM_MAPPING
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


class AcceptOrRejectCheckForm(GARequestErrorReportingMixin, forms.Form):
    """
    CheckForm for accepting or rejecting a check.
    """

    fiu_action = forms.CharField(max_length=10)
    accept_further_details = forms.CharField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['decision_reason'],
    )
    auto_accept_reason = forms.CharField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['auto_accept_reason'],
    )
    reject_further_details = forms.CharField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['decision_reason'],
    )
    fiu_investigation_id = forms.CharField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['fiu_investigation_id'],
    )
    intelligence_report_id = forms.CharField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['intelligence_report_id'],
    )
    other_reason = forms.CharField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['other_reason'],
    )
    payment_source_paying_multiple_prisoners = forms.BooleanField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['payment_source_paying_multiple_prisoners'],
    )
    payment_source_multiple_cards = forms.BooleanField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['payment_source_multiple_cards'],
    )
    payment_source_linked_other_prisoners = forms.BooleanField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['payment_source_linked_other_prisoners'],
    )
    payment_source_known_email = forms.BooleanField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['payment_source_known_email'],
    )
    payment_source_unidentified = forms.BooleanField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['payment_source_unidentified'],
    )
    prisoner_multiple_payments_payment_sources = forms.BooleanField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['prisoner_multiple_payments_payment_sources'],
    )
    human_readable_names = CHECK_DETAIL_FORM_MAPPING['rejection_reasons']
    error_messages = {
        'missing_reject_reason': _('You must provide a reason for rejecting a credit'),
        'reject_with_accept_details': _('You cannot reject with the Add Further Details box under accept populated'),
        'reject_with_auto_accept': _(
            'You cannot reject with the Automatically Accept Future Credits box under accept populated'
        ),
        'accept_with_reject_details': _('You cannot accept with the Add Further Details box under reject populated'),
        'accept_with_reject_reason': _('You must untick all rejection fields before accepting a credit'),
    }

    def __init__(self, object_id, request, **kwargs):
        super().__init__(**kwargs)
        self.object_id = object_id
        self.need_attention_date = get_need_attention_date()
        self.request = request

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
            for rejection_field in self.human_readable_names.keys()
        ])

    def clean(self):
        """
        Makes sure that the check is in the correct state and validate field combination.
        """
        status = self.cleaned_data['fiu_action']
        further_details = ''

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
            if self.cleaned_data.get('auto_accept_reason'):
                self.add_error(
                    'auto_accept_reason',
                    self.error_messages['reject_with_auto_accept']
                )
            further_details = self.cleaned_data['reject_further_details']

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
            further_details = self.cleaned_data['accept_further_details']

        if not self.errors:
            # We don't want to propagate false-y (i.e. False, or empty string) values to API so we filter on
            # truthiness of form values
            self.data_payload = {
                'decision_reason': further_details,
            }

            if status == 'reject':
                self.data_payload['rejection_reasons'] = dict(
                    item
                    for item in self.cleaned_data.items()
                    if item[1] and item[0] in self.human_readable_names.keys()
                )
        return super().clean()

    def get_resolve_endpoint_path(self, fiu_action='accept'):
        return f'/security/checks/{self.object_id}/{fiu_action}/'

    def _handle_request_exception(self, e: RequestException, entity: str) -> bool:
        try:
            error_payload = e.response.json()
        except Exception:
            error_payload = {}
        logger.exception('%s %s could not be actioned. Error payload: %s', entity, self.object_id, error_payload)
        self.add_error(None, _('There was an error with your request.'))
        return False

    def accept_or_reject(self):
        """
        Accepts or rejects the check via the API.
        :return: True if the API call was successful.
            If not, it returns False and populating the self.errors dict.
        """
        fiu_action = self.cleaned_data.pop('fiu_action')
        endpoint = self.get_resolve_endpoint_path(fiu_action=fiu_action)

        # TODO figure out what we should do in the case that we are unable to persist the auto-accept rule.
        # Should we revert the state of the check via an update?
        try:
            self.session.post(
                endpoint,
                json=self.data_payload
            )
        except RequestException as e:
            return self._handle_request_exception(e, 'Check')
        else:
            if fiu_action == 'accept' and self.cleaned_data.get('auto_accept_reason'):
                # This shouldn't make another request due to the lru_cache decorator
                check = self.get_object()
                check_auto_accept_rule_state = check.get('auto_accept_rule_state', {})
                check_auto_accept_rule_id = None
                if check_auto_accept_rule_state:
                    check_auto_accept_rule_id = check_auto_accept_rule_state['auto_accept_rule']
                try:
                    if check_auto_accept_rule_id:
                        # There is an auto-accept rule, which may be in the active or inactive state
                        self.session.patch(
                            f'/security/checks/auto-accept/{check_auto_accept_rule_id}',
                            json={
                                'states': [{
                                    'active': True,
                                    'reason': self.cleaned_data.get('auto_accept_reason')
                                }]
                            }
                        )
                    else:
                        self.session.post(
                            '/security/checks/auto-accept',
                            json={
                                'prisoner_profile': check['credit']['prisoner_profile'],
                                'debit_card_sender_details': check['credit']['billing_address'][
                                    'debit_card_sender_details'
                                ],
                                'states': [{
                                    'reason': self.cleaned_data.get('auto_accept_reason')
                                }]
                            }
                        )

                except RequestException as e:
                    return self._handle_request_exception(e, 'Auto Accept Rule')
            return True


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
