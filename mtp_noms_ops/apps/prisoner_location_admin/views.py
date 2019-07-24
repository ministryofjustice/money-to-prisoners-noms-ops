from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import gettext, ngettext
from django.views.generic.edit import FormView
from mtp_common.spooling import spooler

from prisoner_location_admin.forms import LocationFileUploadForm


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
            form.update_locations()
            location_count = len(form.cleaned_data['location_file'])
            transfer_count = form.cleaned_data['transfer_count']
            skipped_counts = form.cleaned_data['skipped_counts']

            if settings.ASYNC_LOCATION_UPLOAD and spooler.installed:
                messages.info(self.request, ' '.join([
                    ngettext(
                        '%d prisoner location scheduled for upload.',
                        '%d prisoner locations scheduled for upload.',
                        location_count
                    ) % location_count,
                    gettext('You will receive an email notification if the upload fails.')
                ]))
            else:
                messages.info(self.request, ngettext(
                    '%d prisoner location updated successfully',
                    '%d prisoner locations updated successfully',
                    location_count
                ) % location_count)

            message_parts = []
            if transfer_count:
                message_parts.append(ngettext(
                    'Ignored %(number)d prisoner in transfer.',
                    'Ignored %(number)d prisoners in transfer.',
                    transfer_count
                ) % {
                    'number': transfer_count,
                })
            if skipped_counts:
                prisons = ', '.join(sorted(skipped_counts.keys()))
                skipped_count = sum(skipped_counts.values())
                message_parts.append(ngettext(
                    'Ignored %(number)d prisoner in unsupported prison (NOMIS code: %(prisons)s).',
                    'Ignored %(number)d prisoners in unsupported prisons (NOMIS codes: %(prisons)s).',
                    skipped_count
                ) % {
                    'number': skipped_count,
                    'prisons': prisons,
                })
            if message_parts:
                messages.warning(self.request, ' '.join(message_parts))

            return super().form_valid(form)
        except forms.ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
