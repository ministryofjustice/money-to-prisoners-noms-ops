from django import forms
from django.utils.translation import gettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin


class HMPPSEmployeeForm(GARequestErrorReportingMixin, forms.Form):
    next = forms.CharField(required=False)
    confirmation = forms.ChoiceField(
        label=_('Are you a direct employee of HMPPS working in an intelligence function?'),
        required=True, choices=(
            ('yes', _('Yes')),
            ('no', _('No')),
        ), error_messages={
            'required': _('Please select ‘yes’ or ‘no’'),
        }
    )
