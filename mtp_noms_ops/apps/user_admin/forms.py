from django import forms
from django.utils.translation import gettext_lazy as _
from mtp_common.user_admin.forms import UserUpdateForm as UserUpdateFormBase


class UserUpdateForm(UserUpdateFormBase):
    user_admin = forms.BooleanField(
        label=_('This account is for an FIU user (FIU users will be able to manage other user accounts)'),
        required=False,
    )
