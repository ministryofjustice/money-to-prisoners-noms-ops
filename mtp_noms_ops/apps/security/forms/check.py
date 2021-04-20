import logging
from functools import lru_cache

from django import forms
from django.contrib import messages
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth.api_client import get_api_session
from requests.exceptions import RequestException

from security.constants import CHECK_DETAIL_FORM_MAPPING, CHECK_AUTO_ACCEPT_UNIQUE_CONSTRAINT_ERROR
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


class AutoAcceptListForm(SecurityForm):
    """
    List of AutoAccepts checks.
    """
    ordering = forms.ChoiceField(
        label=_('Order by'),
        required=False,
        initial='-states__created',
        choices=[
            ('states__created', _('Date started (oldest to newest)')),
            ('-states__created', _('Date started (newest to oldest)')),
            ('states__added_by__first_name', _('Forename of person who last activated (lexical order)')),
            ('-states__added_by__first_name', _('Forename of person who last activated (reverse lexical order)')),
        ],
    )

    def __init__(self, request, **kwargs):
        super().__init__(request, **kwargs)
        self.my_list_count = 0

    def get_api_request_params(self):
        """
        Gets all checks where last associated state created has active = True
        """
        params = super().get_api_request_params()
        params['is_active'] = True
        return params

    def get_object_list_endpoint_path(self):
        return '/security/checks/auto-accept/'

    def get_check_list_endpoint_path(self):
        return '/security/checks/'

    def get_object_list(self):
        """
        Gets objects, converts datetimes found in them.
        """
        object_list = convert_date_fields(super().get_object_list(), include_nested=True)
        self.my_list_count = self.session.get(self.get_check_list_endpoint_path(), params={
            'status': 'pending',
            'credit_resolution': 'initial',
            'assigned_to': self.request.user.pk,
            'offset': 0,
            'limit': 1
        }).json()['count']
        self.initial_index = ((self.cleaned_data.get('page', 1) - 1) * self.page_size) + 1
        self.final_index = min(
            self.cleaned_data.get('page', 1) * self.page_size,
            self.total_count
        )
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
    auto_accept = forms.BooleanField(
        required=False,
        label=_('Automatically accept future credits'),  # label is replaced in template
        help_text=_('They will be flagged in decision history'),
    )
    auto_accept_reason = forms.CharField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['auto_accept_reason'],
    )
    reject_further_details = forms.CharField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['decision_reason'],
    )
    has_fiu_investigation_id = forms.BooleanField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['fiu_investigation_id'],
    )
    fiu_investigation_id = forms.CharField(
        required=False,
        label=_('Give FIU reference'),
    )
    has_intelligence_report_id = forms.BooleanField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['intelligence_report_id'],
    )
    intelligence_report_id = forms.CharField(
        required=False,
        label=_('Give reference'),
    )
    has_other_reason = forms.BooleanField(
        required=False,
        label=CHECK_DETAIL_FORM_MAPPING['rejection_reasons']['other_reason'],
    )
    other_reason = forms.CharField(
        required=False,
        label=_('Give the reason'),
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

    # conditional fields that are hidden behind checkboxes are not required by default
    # however if the checkbox is checked they are required
    conditional_fields = {
        'auto_accept': ['auto_accept_reason'],
        'has_fiu_investigation_id': ['fiu_investigation_id'],
        'has_intelligence_report_id': ['intelligence_report_id'],
        'has_other_reason': ['other_reason'],
    }

    error_messages = {
        'missing_reject_reason': _('You must provide a reason for rejecting a credit'),
        'missing_details': _('You must provide details'),
        'reject_with_accept_details': _(
            "You have added details in the 'accept' box. You cannot reject a credit with this box filled"),
        'reject_with_auto_accept': _(
            "You have ticked 'auto-accept' and given a reason for this in the text box. "
            'You cannot reject a credit with these ticked and filled.'
        ),
        'accept_with_reject_details': _(
            "You have added details in the 'reject' box. You cannot accept a credit with this box filled."
        ),
        'accept_with_reject_reason': _("You cannot accept a credit when you have ticked any of the 'reject' tickboxes.")
    }

    def __init__(self, object_id, request, **kwargs):
        super().__init__(**kwargs)
        self.object_id = object_id
        self.need_attention_date = get_need_attention_date()
        self.request = request
        self.data_payload = None

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
        except RequestException as e:
            self._handle_request_exception(e, 'Check')
            return None

    def get_object_endpoint_path(self):
        return f'/security/checks/{self.object_id}/'

    @cached_property
    def session(self):
        return get_api_session(self.request)

    def is_reject_reason_populated(self):
        return any(
            self.cleaned_data.get(rejection_field)
            for rejection_field in CHECK_DETAIL_FORM_MAPPING['rejection_reasons']
        )

    def clean(self):
        """
        Makes sure that the check is in the correct state and validate field combination.
        """
        status = self.cleaned_data['fiu_action']
        further_details = ''

        if not self.errors:  # if already in error => skip
            if self.get_object()['status'] != 'pending':
                raise forms.ValidationError(
                    _("You cannot action this credit because it is not in 'pending'.")
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

        self._clean_conditional_fields()

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
                    if item[1] and item[0] in CHECK_DETAIL_FORM_MAPPING['rejection_reasons']
                )
        return super().clean()

    def _clean_conditional_fields(self):
        # validate conditional subfields controlled by checkboxes
        for conditional_checkbox_field, conditional_subfields in self.conditional_fields.items():
            if not self.cleaned_data.get(conditional_checkbox_field):
                # checkbox not selected, subfields are not required
                # TODO: should probably remove subfield values from self.cleaned_data
                #       in case javascript is disabled and hence disabled property was not set correctly on subfields
                continue

            # checkbox was selected, ensure all subfields are provided
            all_subfields_valid = True
            for conditional_subfield in conditional_subfields:
                if not self.cleaned_data.get(conditional_subfield):
                    all_subfields_valid = False
                    # if subfield missing, add an error
                    self.add_error(
                        conditional_subfield,
                        self.fields[conditional_subfield].error_messages['required']
                    )
            if not all_subfields_valid:
                # if any subfield missing, add an error
                self.add_error(
                    conditional_checkbox_field,
                    self.error_messages['missing_details']
                )

    def get_resolve_endpoint_path(self, fiu_action='accept'):
        return f'/security/checks/{self.object_id}/{fiu_action}/'

    def _handle_request_exception(self, e: RequestException, entity: str) -> tuple:
        error_payload = self._get_request_exception_payload(e)
        return self._render_error_response(error_payload, entity)

    def _render_error_response(self, error_payload, entity):
        logger.exception(
            f'{entity} %(object_id)s could not be actioned. Error payload: %(exception)r',
            {'object_id': self.object_id, 'exception': error_payload}
        )
        self.add_error(None, _('There was an error with your request.'))
        return (False, '')

    def _get_request_exception_payload(self, e: RequestException) -> dict:
        try:
            error_payload = e.response.json()
        except Exception:
            error_payload = {}
        return error_payload

    def accept_or_reject(self):
        """
        Accepts or rejects the check via the API.
        :rtype tuple(bool, str)
        :returns: First element: True if the API call was successful. If not, False
                  Second element: Additional information string to populate as message or empty string
        """
        fiu_action = self.cleaned_data.pop('fiu_action')
        endpoint = self.get_resolve_endpoint_path(fiu_action=fiu_action)

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
                if check_auto_accept_rule_id:
                    try:
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
                    except RequestException as e:
                        return self._handle_request_exception(e, 'Auto Accept Rule')
                else:
                    try:
                        self.session.post(
                            '/security/checks/auto-accept',
                            json={
                                'prisoner_profile_id': check['credit']['prisoner_profile'],
                                'debit_card_sender_details_id': check['credit']['billing_address'][
                                    'debit_card_sender_details'
                                ],
                                'states': [{
                                    'reason': self.cleaned_data.get('auto_accept_reason')
                                }]
                            }
                        )
                    except RequestException as e:
                        error_response = self._get_request_exception_payload(e)
                        if any(
                                [
                                    error_string == CHECK_AUTO_ACCEPT_UNIQUE_CONSTRAINT_ERROR
                                    for error_string in error_response.get('non_field_errors', [])
                                ]
                        ):
                            # TODO we happy that this check won't be linked to the existing auto-accept rule in the UI?
                            return (
                                True,
                                'The auto-accept could not be created because an auto-accept '
                                'already exists for {sender_name} and {prisoner_number}'.format(
                                    sender_name=check['credit']['sender_name'],
                                    prisoner_number=check['credit']['prisoner_number']
                                )
                            )
                        else:
                            return self._handle_request_exception(e, 'Auto Accept Rule')
            return (True, '')


class AutoAcceptDetailForm(forms.Form):
    deactivation_reason = forms.CharField(label='Give reason why auto accept is to stop')

    def __init__(self, object_id, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request
        self.object_id = object_id

    def get_object_list_endpoint_path(self):
        return '/security/checks/auto-accept/'

    def get_deactivate_endpoint_path(self):
        return f'/security/checks/auto-accept/{self.object_id}/'

    @cached_property
    def session(self):
        return get_api_session(self.request)

    def deactivate_auto_accept_rule(self):
        """
        Deactivates auto accept rule via the API.
        :returns: True if the API call was successful. If not, False
        """
        endpoint = self.get_deactivate_endpoint_path()
        try:
            # There is an auto-accept rule, which may be in the active or inactive state
            self.session.patch(
                endpoint,
                json={
                    'states': [{
                        'active': False,
                        'reason': self.cleaned_data['deactivation_reason']
                    }]
                }
            )
        except RequestException as e:
            try:
                error_payload = e.response.json()
            except Exception:
                error_payload = {}
            logger.exception(
                'Auto-accept deactivation could not be actioned. Error payload: %(exception)r',
                {'exception': error_payload}
            )
            self.add_error(None, _('There was an error with your request.'))

            return False
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
        else:
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
            logger.exception('Check %(check_id)s could not be assigned', {'check_id': self.object_id})
            messages.add_message(
                self.request,
                messages.ERROR,
                msg
            )
            return False
