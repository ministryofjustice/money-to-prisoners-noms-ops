from django.views.generic.edit import FormView
from django.core.urlresolvers import reverse_lazy

from .forms import LocationFileUploadForm


class LocationFileUploadView(FormView):
    template_name = 'prisoner_location_admin/location_file_upload.html'
    form_class = LocationFileUploadForm
    success_url = reverse_lazy('dashboard')

    def get_form_kwargs(self):
        kwargs = super(LocationFileUploadView, self).get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.update_locations()
        return super(LocationFileUploadView, self).form_valid(form)
