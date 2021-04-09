from mtp_common.user_admin.views import AcceptRequestView as AcceptRequestViewBase

from .forms import AcceptRequestForm


class AcceptRequestView(AcceptRequestViewBase):
    form_class = AcceptRequestForm
