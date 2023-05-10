from django import forms
from django.utils.translation import gettext_lazy as _


class HMPPSEmployeeForm(forms.Form):
    next = forms.CharField(required=False)
    confirmation = forms.ChoiceField(
        label=_('Are you a direct employee of HMPPS or a contracted prison and working in an intelligence function?'),
        required=True, choices=(
            ('yes', _('Yes')),
            ('no', _('No')),
        ), error_messages={
            'required': _('Please select ‘yes’ or ‘no’'),
        }
    )
