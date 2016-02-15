import csv
from datetime import datetime
import io
import logging
import re

from django import forms
from django.utils.translation import ugettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from slumber.exceptions import HttpClientError

from moj_auth import api_client

logger = logging.getLogger('mtp')

EXPECTED_ROW_LENGTH = 5
DOB_PATTERN = re.compile(
    '([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}).*'
)
DATE_FORMATS = ['%d/%m/%Y', '%d/%m/%y']


class LocationFileUploadForm(GARequestErrorReportingMixin, forms.Form):
    location_file = forms.FileField(required=True, label='')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(LocationFileUploadForm, self).__init__(*args, **kwargs)

    def clean_location_file(self):
        locations = []

        if not self.cleaned_data['location_file'].name.endswith('.csv'):
            raise forms.ValidationError(_('Uploaded file must be a CSV'))

        location_reader = csv.reader(
            io.StringIO(self.cleaned_data['location_file'].read().decode('utf-8')))

        first_row = True
        invalid_row = None
        for row in location_reader:
            # skip header row
            if first_row:
                first_row = False
                continue

            if len(row) != EXPECTED_ROW_LENGTH:
                invalid_row = row
                continue
            # On next pass through the loop, if next line is valid,
            # raise error as short/long row found before end of file
            # (as we expect some non-data rows at the end, but not in the middle)
            if invalid_row is not None:
                raise forms.ValidationError(
                    _('Row has %s columns, should have %s: %s')
                    % (len(invalid_row), EXPECTED_ROW_LENGTH, invalid_row)
                )

            # parse dob
            m = DOB_PATTERN.match(row[3])
            dt = None
            if m:
                for format in DATE_FORMATS:
                    try:
                        dt = datetime.strptime(m.groups()[0], format)
                        break
                    except ValueError:
                        pass

            if dt is None:
                raise forms.ValidationError(
                    _('Date of birth "%s" is not in a valid format' % row[3]))

            locations.append({
                'prisoner_number': row[0],
                'prisoner_name': ' '.join([row[2], row[1]]),
                'prisoner_dob': dt.strftime('%Y-%m-%d'),
                'prison': row[4],
            })

        if len(locations) == 0:
            raise forms.ValidationError(
                _('Location file does not seem to contain any valid rows'))

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
