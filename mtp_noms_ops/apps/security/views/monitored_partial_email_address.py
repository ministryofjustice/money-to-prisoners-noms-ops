from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import BaseFormView, FormView

from security.forms.monitored_partial_email_address import (
    MonitoredPartialEmailAddressListForm,
    MonitoredPartialEmailAddressAddForm,
    MonitoredPartialEmailAddressDeleteForm,
)
from security.views.object_base import SecurityView


class MonitoredPartialEmailAddressListView(SecurityView):
    """
    View list of monitored partial email addresses
    """
    title = _('Monitored email addresses')
    template_name = 'security/monitored-email-address-list.html'
    form_class = MonitoredPartialEmailAddressListForm


class MonitoredPartialEmailAddressAddView(SecurityView):
    """
    Add a new monitored partial email address
    """
    title = _('Add a keyword to monitor')
    template_name = 'security/monitored-email-address-add.html'
    form_class = MonitoredPartialEmailAddressAddForm
    success_url = reverse_lazy('security:monitored_email_addresses')

    def _get_breadcrumbs(self, **kwargs):
        breadcrumbs = super()._get_breadcrumbs(**kwargs)
        breadcrumbs.insert(-1, {
            'name': _('Monitored email addresses'),
            'url': reverse('security:monitored_email_addresses'),
        })
        return breadcrumbs

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        if self.request.method == 'GET':
            form_kwargs.pop('data', None)
        elif self.request.method == 'POST':
            form_kwargs['data'] = self.request.POST
        return form_kwargs

    def form_valid(self, form):
        keyword = form.cleaned_data['keyword']
        if form.add_keyword():
            messages.info(self.request, _('“%(keyword)s” has been added') % {'keyword': keyword})
        else:
            messages.error(self.request, _('Keyword “%(keyword)s” could not be added.') % {'keyword': keyword})
        return HttpResponseRedirect(self.get_success_url())

    get = FormView.get


class MonitoredPartialEmailAddressDeleteView(BaseFormView):
    """
    Remove a monitored partial email address
    """
    form_class = MonitoredPartialEmailAddressDeleteForm
    success_url = reverse_lazy('security:monitored_email_addresses')

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs.update(
            request=self.request,
        )
        return form_kwargs

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(self.get_success_url())

    def form_valid(self, form: MonitoredPartialEmailAddressDeleteForm):
        keyword = form.cleaned_data['keyword']
        if form.delete_keyword():
            messages.info(self.request, _('“%(keyword)s” has been removed') % {'keyword': keyword})
        else:
            messages.error(self.request, _('Keyword “%(keyword)s” could not be removed.') % {'keyword': keyword})
        return super().form_valid(form)
