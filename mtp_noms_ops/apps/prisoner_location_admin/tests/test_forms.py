import logging
from unittest import mock

from django.core.urlresolvers import reverse
from django.test import RequestFactory, override_settings

from prisoner_location_admin.forms import LocationFileUploadForm
from security.tests import silence_logger
from . import (
    PrisonerLocationUploadTestCase, generate_testable_location_data,
    get_csv_data_as_file
)


class LocationFileUploadFormTestCase(PrisonerLocationUploadTestCase):

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

    def test_location_file_valid_excel_format(self):
        file_data, _ = generate_testable_location_data(excel_csv=True)

        request = self.factory.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file(file_data)}
        )
        form = LocationFileUploadForm(request.POST, request.FILES, request=request)

        self.assertTrue(form.is_valid())

    def test_location_file_skips_transfer_records(self):
        file_data, _ = generate_testable_location_data(
            length=20, extra_row='A1234ZZ,Smith,John,2/9/1997 00:00,TRN'
        )

        request = self.factory.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file(file_data)}
        )
        form = LocationFileUploadForm(request.POST, request.FILES, request=request)

        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.cleaned_data['location_file']), 20)
        for location in form.cleaned_data['location_file']:
            self.assertNotEqual(location['prison'], 'TRN')

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
            ['The file has the wrong number of columns']
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
            ["The submitted file is empty"]
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

    @override_settings(UPLOAD_REQUEST_PAGE_SIZE=10)
    @mock.patch('prisoner_location_admin.tasks.api_client')
    def test_location_file_batch_upload(self, mock_api_client):
        create_conn = mock_api_client.get_authenticated_connection().prisoner_locations
        delete_inactive_conn = create_conn.actions.delete_inactive
        delete_old_conn = create_conn.actions.delete_old

        file_data, expected_data = generate_testable_location_data(length=50)

        auth_response = self.login()
        request = self.factory.post(
            reverse('location_file_upload'),
            {'location_file': get_csv_data_as_file(file_data)}
        )
        request.user = mock.MagicMock()
        request.user.user_data = auth_response['user_data']
        form = LocationFileUploadForm(request.POST, request.FILES, request=request)

        self.assertTrue(form.is_valid())
        with silence_logger(name='mtp', level=logging.WARNING):
            form.update_locations()

        delete_inactive_conn.post.assert_called_once_with()
        create_conn.post.assert_has_calls([
            mock.call(expected_data[0:10]),
            mock.call(expected_data[10:20]),
            mock.call(expected_data[20:30]),
            mock.call(expected_data[30:40]),
            mock.call(expected_data[40:50]),
        ])
        delete_old_conn.post.assert_called_once_with()
