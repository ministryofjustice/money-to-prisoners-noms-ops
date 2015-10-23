from django.views.generic.edit import FormView
from django.core.urlresolvers import reverse_lazy
from django import forms
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

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
            form.update_locations()
            messages.add_message(self.request, messages.SUCCESS,
                                 _('File uploaded successfully!'))
            return super(LocationFileUploadView, self).form_valid(form)
        except forms.ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
