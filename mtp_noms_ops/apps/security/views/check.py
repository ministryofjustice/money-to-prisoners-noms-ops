from django.contrib import messages
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy

from security.forms.check import AcceptCheckForm, CheckListForm
from security.views.object_base import SecurityDetailView, SecurityView


class CheckListView(SecurityView):
    """
    View returning the checks in pending status.
    """
    title = gettext_lazy('Payments pending')
    template_name = 'security/checks_list.html'
    form_class = CheckListForm


class AcceptCheckView(SecurityDetailView):
    """
    View accepting a check in pending status.
    """
    object_list_context_key = 'checks'

    list_title = gettext_lazy('Payments pending')
    template_name = 'security/accept_check.html'
    form_class = AcceptCheckForm
    id_kwarg_name = 'check_id'
    object_context_key = 'check'
    list_url = reverse_lazy('security:check_list')

    def get_title_for_object(self, detail_object):
        return gettext_lazy('Accept this payment')

    def form_valid(self, form):
        if self.request.method == 'POST':
            result = form.accept()
            if not result:
                return self.form_invalid(form)

            messages.add_message(
                self.request,
                messages.INFO,
                gettext_lazy('Payment accepted'),
            )
            return HttpResponseRedirect(self.list_url)

        return super().form_valid(form)
