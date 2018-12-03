import collections
import csv
from datetime import datetime
import io
import re

from django import forms
from django.utils.translation import ugettext_lazy as _
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.auth.api_client import get_api_session

from prisoner_location_admin.tasks import update_locations
from security.models import PrisonList

EXPECTED_ROW_LENGTH = 5
DOB_PATTERN = re.compile(
    r'(?P<dob>\d{1,2}/\d{1,2}/\d{2,4}).*'
)
DATE_FORMATS = ['%d/%m/%Y', '%d/%m/%y']


class LocationFileUploadForm(GARequestErrorReportingMixin, forms.Form):
    location_file = forms.FileField(
        label=_('Location file'),
        error_messages={'required': _('Please choose a file')},
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def get_supported_prisons(self):
        session = get_api_session(self.request)
        prison_list = PrisonList(session)
        return set(prison['nomis_id'] for prison in prison_list.prisons)

    def clean_location_file(self):
        locations = []
        transfer_count = 0
        skipped_counts = collections.defaultdict(int)

        if not self.cleaned_data['location_file'].name.lower().endswith('.csv'):
            raise forms.ValidationError(_('Uploaded file must be a CSV'))

        try:
            location_file = io.StringIO(self.cleaned_data['location_file'].read().decode())
        except UnicodeDecodeError:
            raise forms.ValidationError(_('Can’t read CSV file'))

        supported_prisons = self.get_supported_prisons()

        first_row = True
        invalid_row = None
        for row in csv.reader(location_file):
            # skip header row
            if first_row:
                first_row = False
                continue

            if len(row) != EXPECTED_ROW_LENGTH or row[1] == row[2] == row[3] == row[4] == '':
                invalid_row = row
                continue
            # On next pass through the loop, if next line is valid,
            # raise error as short/long row found before end of file
            # (as we expect some non-data rows at the end, but not in the middle)
            if invalid_row is not None:
                raise forms.ValidationError(_('The file has the wrong number of columns'))

            if row[4] == 'TRN':
                # skip transfer records
                transfer_count += 1
                continue
            if row[4] not in supported_prisons:
                # skip records with unknown prison
                skipped_counts[row[4]] += 1
                continue

            dob = parse_dob(row[3])

            locations.append({
                'prisoner_number': row[0],
                'prisoner_name': ' '.join([row[2], row[1]]),
                'prisoner_dob': dob,
                'prison': row[4],
            })

        if len(locations) == 0:
            raise forms.ValidationError(_('The uploaded report contains no valid prisoner locations'))

        self.cleaned_data['transfer_count'] = transfer_count
        self.cleaned_data['skipped_counts'] = skipped_counts
        return locations

    def update_locations(self):
        locations = self.cleaned_data['location_file']
        if locations:
            update_locations(user=self.request.user, locations=locations)


def parse_dob(dob):
    dob_matches = DOB_PATTERN.match(dob)
    dob = None
    if dob_matches:
        for date_format in DATE_FORMATS:
            try:
                dob = datetime.strptime(dob_matches.group('dob'), date_format)
                break
            except ValueError:
                pass

    if dob is None:
        raise forms.ValidationError(_('Date of birth "%s" is not in a valid format' % dob))

    return dob.strftime('%Y-%m-%d')
