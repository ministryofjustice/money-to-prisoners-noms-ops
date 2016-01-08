import csv
import io
import logging

from django import forms
from django.utils.translation import ugettext_lazy as _
from slumber.exceptions import HttpClientError

from moj_auth import api_client

logger = logging.getLogger()

EXPECTED_ROW_LENGTH = 4


class LocationFileUploadForm(forms.Form):
    location_file = forms.FileField(required=True, label='')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(LocationFileUploadForm, self).__init__(*args, **kwargs)

    def clean_location_file(self):
        locations = []

        if not self.cleaned_data['location_file'].name.endswith('.csv'):
            raise forms.ValidationError(_("Uploaded file must be a CSV"))

        location_reader = csv.reader(
            io.StringIO(self.cleaned_data['location_file'].read().decode('utf-8')))
        for row in location_reader:
            if len(row) != EXPECTED_ROW_LENGTH:
                raise forms.ValidationError(
                    _("Row has %s columns, should have %s: %s")
                    % (len(row), EXPECTED_ROW_LENGTH, row))

            locations.append({
                'prisoner_name': row[0],
                'prisoner_number': row[1],
                'prisoner_dob': row[2],
                'prison': row[3],
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
        except HttpClientError as e:
            logger.exception('Prisoner locations failed to upload')
            raise forms.ValidationError(e.content)

        logger.info('Prisoner locations updated')
