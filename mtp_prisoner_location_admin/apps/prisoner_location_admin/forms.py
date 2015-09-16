import csv
import io

from django import forms
from django.utils.translation import ugettext_lazy as _
from slumber.exceptions import SlumberHttpBaseException

from moj_auth import api_client

EXPECTED_ROW_LENGTH = 3


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
            if len(row) != EXPECTED_ROW_LENGTH:
                raise forms.ValidationError(
                    _("Row has %s values, should have %s: %s"
                        % (len(row), EXPECTED_ROW_LENGTH, row)))

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

        try:
            client.prisoner_locations.post(locations)
        except SlumberHttpBaseException as e:
            raise forms.ValidationError(e.content)
