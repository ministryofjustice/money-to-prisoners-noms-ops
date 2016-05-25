import csv
from datetime import datetime
import io
import logging
import re

from django import forms
from django.utils.translation import ugettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth import api_client
from slumber.exceptions import HttpClientError

logger = logging.getLogger('mtp')

EXPECTED_ROW_LENGTH = 5
DOB_PATTERN = re.compile(
    '([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}).*'
)
DATE_FORMATS = ['%d/%m/%Y', '%d/%m/%y']


class LocationFileUploadForm(GARequestErrorReportingMixin, forms.Form):
    location_file = forms.FileField(label=_('Location file'),
                                    error_messages={
                                        'required': _('Please choose a file'),
                                    })

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(LocationFileUploadForm, self).__init__(*args, **kwargs)

    def clean_location_file(self):
        locations = []

        if not self.cleaned_data['location_file'].name.lower().endswith('.csv'):
            raise forms.ValidationError(_('Uploaded file must be a CSV'))

        try:
            location_file = io.StringIO(self.cleaned_data['location_file'].read().decode('utf-8'))
        except UnicodeDecodeError:
            raise forms.ValidationError(_('Can’t read CSV file'))

        first_row = True
        invalid_row = None
        for row in csv.reader(location_file):
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
                raise forms.ValidationError(_('The file has the wrong number of columns'))

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
                _('The file doesn’t contain valid rows'))

        return locations

    def update_locations(self):
        locations = self.cleaned_data['location_file']
        client = api_client.get_connection(self.request)
        user = self.request.user
        username = user.user_data.get('username', 'Unknown')
        user_description = user.get_full_name()
        if user_description:
            user_description += ' (%s)' % username
        else:
            user_description = username

        try:
            client.prisoner_locations.post(locations)
        except HttpClientError as e:
            logger.exception('Prisoner locations update by %s failed!' % user_description)
            raise forms.ValidationError(e.content)

        location_count = len(locations)
        logger.info('%d prisoner locations updated successfully by %s' % (
            location_count,
            user_description,
        ), extra={
            'elk_fields': {
                '@fields.prisoner_location_count': location_count,
                '@fields.username': username,
            }
        })
        return location_count
