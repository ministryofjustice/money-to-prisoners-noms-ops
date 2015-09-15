import csv
import io

from django import forms
from django.utils.translation import ugettext_lazy as _

from moj_auth import api_client


class LocationFileUploadForm(forms.Form):
    location_file = forms.FileField(required=True)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(LocationFileUploadForm, self).__init__(*args, **kwargs)

    def clean_location_file(self):
        locations = []
        location_reader = csv.reader(
            io.StringIO(self.cleaned_data['location_file'].read().decode('utf-8')))
        for row in location_reader:
            if len(row) != 3:
                raise forms.ValidationError(
                    _("Location file contains an invalid row"))

            locations.append({
                'prisoner_number': row[0],
                'prisoner_dob': row[1],
                'prison': row[2]
            })

        if len(locations) == 0:
            raise forms.ValidationError(
                _("Location file does not seem to contain any valid rows"))

        return locations

    def update_locations(self):
        locations = self.cleaned_data['location_file']
        client = api_client.get_connection(self.request)
        client.prisoner_locations.post(locations)
