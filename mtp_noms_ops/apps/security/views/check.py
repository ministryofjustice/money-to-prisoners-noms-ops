from django.contrib import messages
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import gettext_lazy
from django.views.generic.edit import FormView

from security.forms.check import AcceptCheckForm, CheckListForm, RejectCheckForm
from security.views.object_base import SecurityView


class CheckListView(SecurityView):
    """
    View returning the checks in pending status.
    """
    title = gettext_lazy('Credits pending')
    template_name = 'security/checks_list.html'
    form_class = CheckListForm


class ActionCheckView(FormView):
    """
    View rejecting a check in pending status.
    """
    object_list_context_key = 'checks'

    list_title = gettext_lazy('Credits pending')
    id_kwarg_name = 'check_id'
    object_context_key = 'check'
    list_url = reverse_lazy('security:check_list')

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs.update(
            {
                'request': self.request,
                'object_id': self.kwargs[self.id_kwarg_name],
            },
        )
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        detail_object = context_data['form'].get_object()
        if detail_object is None:
            raise Http404('Detail object not found')

        # keep query string in breadcrumbs
        list_url = self.request.build_absolute_uri(str(self.list_url))
        referrer_url = self.request.META.get('HTTP_REFERER', '-')
        if referrer_url.split('?', 1)[0] == list_url:
            list_url = referrer_url

        context_data['breadcrumbs'] = [
            {'name': gettext_lazy('Home'), 'url': reverse('security:dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': self.title},
        ]
        context_data[self.object_context_key] = detail_object

        return context_data


class AcceptCheckView(ActionCheckView):
    """
    View accepting a check in pending status.
    """
    title = gettext_lazy('Accept this credit')
    template_name = 'security/accept_check.html'
    form_class = AcceptCheckForm

    def form_valid(self, form):
        if self.request.method == 'POST':
            result = form.accept()
            if not result:
                return self.form_invalid(form)

            messages.add_message(
                self.request,
                messages.INFO,
                gettext_lazy('Credit accepted'),
            )
            return HttpResponseRedirect(self.list_url)

        return super().form_valid(form)


class RejectCheckView(ActionCheckView):
    """
    View rejecting a check in pending status.
    """
    title = gettext_lazy('Reject this credit')
    template_name = 'security/reject_check.html'
    form_class = RejectCheckForm

    def form_valid(self, form):
        if self.request.method == 'POST':
            result = form.reject()
            if not result:
                return self.form_invalid(form)

            messages.add_message(
                self.request,
                messages.INFO,
                gettext_lazy('Credit rejected'),
            )
            return HttpResponseRedirect(self.list_url)

        return super().form_valid(form)
