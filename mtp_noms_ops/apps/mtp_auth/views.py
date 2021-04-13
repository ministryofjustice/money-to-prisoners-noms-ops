from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from mtp_common.user_admin.views import (
    SignUpView as BaseSignUpView,
    AcceptRequestView as AcceptRequestViewBase,
)

from .forms import AcceptRequestForm, SignUpForm


class AcceptRequestView(AcceptRequestViewBase):
    form_class = AcceptRequestForm


class SignUpView(BaseSignUpView):
    form_class = SignUpForm

    def get_context_data(self, **kwargs):
        kwargs['breadcrumbs_back'] = reverse_lazy('root')

        return super().get_context_data(**kwargs)
