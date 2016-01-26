from django.core.urlresolvers import reverse
from django.test import SimpleTestCase, RequestFactory

from ..forms import LocationFileUploadForm
from . import get_csv_data_as_file, generate_testable_location_data


class LocationFileUploadFormTestCase(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_location_file_valid(self):
        file_data, _ = generate_testable_location_data()

        request = self.factory.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file(file_data)}
        )
        form = LocationFileUploadForm(request.POST, request.FILES, request=request)

        self.assertTrue(form.is_valid())

    def test_location_file_short_row_length_invalid(self):
        file_data, _ = generate_testable_location_data(
            extra_row='A1234GY,Smith,John,2/9/1997 00:00'
        )

        request = self.factory.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file(file_data)}
        )
        form = LocationFileUploadForm(request.POST, request.FILES, request=request)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['location_file'],
            ["Row has 4 columns, should have 5: ['A1234GY', 'Smith', 'John', '2/9/1997 00:00']"]
        )

    def test_location_file_empty_file_invalid(self):
        request = self.factory.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file('')}
        )
        form = LocationFileUploadForm(request.POST, request.FILES, request=request)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['location_file'],
            ["The submitted file is empty."]
        )

    def test_location_file_not_csv_invalid(self):
        file_data, _ = generate_testable_location_data()

        request = self.factory.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file(file_data, 'badfile.exe')}
        )
        form = LocationFileUploadForm(request.POST, request.FILES, request=request)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['location_file'],
            ["Uploaded file must be a CSV"]
        )
