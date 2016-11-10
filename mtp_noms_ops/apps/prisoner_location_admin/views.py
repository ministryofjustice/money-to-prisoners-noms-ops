from django.views.generic.edit import FormView
from django.core.urlresolvers import reverse_lazy
from django import forms
from django.contrib import messages
from django.utils.translation import ungettext, gettext as _

from .forms import LocationFileUploadForm
from .tasks import schedule_locations_update


class LocationFileUploadView(FormView):
    template_name = 'prisoner_location_admin/location_file_upload.html'
    form_class = LocationFileUploadForm
    success_url = reverse_lazy('location_file_upload')

    def get_form_kwargs(self):
        kwargs = super(LocationFileUploadView, self).get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        try:
            location_count = form.update_locations()
            if schedule_locations_update:
                message_parts = [
                    ungettext(
                        '%d prisoner location scheduled for upload.',
                        '%d prisoner locations scheduled for upload.',
                        location_count
                    ) % location_count,
                    _('You will receive an email notification if the upload fails.')
                ]
            else:
                message_parts = [
                    ungettext(
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
