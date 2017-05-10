from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ngettext, gettext as _
from django.views.generic.edit import FormView
from mtp_common.spooling import spooler

from .forms import LocationFileUploadForm


class LocationFileUploadView(FormView):
    template_name = 'prisoner_location_admin/location_file_upload.html'
    form_class = LocationFileUploadForm
    success_url = reverse_lazy('location_file_upload')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        try:
            location_count = form.update_locations()
            if settings.ASYNC_LOCATION_UPLOAD and spooler.installed:
                message_parts = [
                    ngettext(
                        '%d prisoner location scheduled for upload.',
                        '%d prisoner locations scheduled for upload.',
                        location_count
                    ) % location_count,
                    _('You will receive an email notification if the upload fails.')
                ]
            else:
                message_parts = [
                    ngettext(
                        '%d prisoner location updated successfully',
                        '%d prisoner locations updated successfully',
                        location_count
                    ) % location_count,
                ]
            messages.info(self.request, ' '.join(message_parts))
            return super().form_valid(form)
        except forms.ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
