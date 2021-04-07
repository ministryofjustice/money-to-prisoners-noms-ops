from django.utils.translation import gettext_lazy as _
from mtp_common.user_admin.views import UserCreationView as UserCreationViewBase

from .forms import UserUpdateForm



class UserCreationView(UserCreationViewBase):
    title = _('Create a new user account')
    form_class = UserUpdateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['page_title'] = self.title

        return context
