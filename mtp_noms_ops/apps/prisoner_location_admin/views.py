from django.views.generic.edit import FormView
from django.core.urlresolvers import reverse_lazy
from django import forms
from django.contrib import messages
from django.utils.translation import ungettext

from .forms import LocationFileUploadForm


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
            message = ungettext(
                '%d prisoner location updated successfully',
                '%d prisoner locations updated successfully',
                location_count
            ) % location_count
            messages.success(self.request, message)
            return super(LocationFileUploadView, self).form_valid(form)
        except forms.ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
