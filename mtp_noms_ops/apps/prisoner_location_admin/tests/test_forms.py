import json
import logging
from unittest import mock

from django.core.urlresolvers import reverse
from django.test import RequestFactory, override_settings
from mtp_common.test_utils import silence_logger
import responses

from prisoner_location_admin.forms import LocationFileUploadForm
from security.tests import api_url
from security.tests.test_forms import mock_prison_response
from . import (
    PrisonerLocationUploadTestCase, generate_testable_location_data,
    get_csv_data_as_file
)


class LocationFileUploadFormTestCase(PrisonerLocationUploadTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def make_request(self, post_data):
        auth_response = self.login()
        request = self.factory.post(
            reverse('location_file_upload'),
            {'location_file': post_data}
        )
        request.session = mock.MagicMock()
        request.user = mock.MagicMock()
        request.user.user_data = auth_response['user_data']
        return request

    def test_location_file_valid(self):
        file_data, _ = generate_testable_location_data()

        request = self.make_request(get_csv_data_as_file(file_data))
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = LocationFileUploadForm(request.POST, request.FILES, request=request)
            self.assertTrue(form.is_valid())

    def test_location_file_valid_excel_format(self):
        file_data, _ = generate_testable_location_data(excel_csv=True)

        request = self.make_request(get_csv_data_as_file(file_data))
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = LocationFileUploadForm(request.POST, request.FILES, request=request)
            self.assertTrue(form.is_valid())

    def test_location_file_short_row_length_invalid(self):
        file_data, _ = generate_testable_location_data(
            extra_rows=['A1234GY,Smith,John,2/9/1997 00:00']
        )

        request = self.make_request(get_csv_data_as_file(file_data))
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = LocationFileUploadForm(request.POST, request.FILES, request=request)
            self.assertFalse(form.is_valid())

        self.assertEqual(
            form.errors['location_file'],
            ['The file has the wrong number of columns']
        )

    def test_location_file_empty_file_invalid(self):
        request = self.make_request(get_csv_data_as_file(''))
        with responses.RequestsMock():
            # does not load prison list
            form = LocationFileUploadForm(request.POST, request.FILES, request=request)
            self.assertFalse(form.is_valid())

        self.assertEqual(
            form.errors['location_file'],
            ['The submitted file is empty']
        )

    def test_location_file_not_csv_invalid(self):
        file_data, _ = generate_testable_location_data()

        request = self.make_request(get_csv_data_as_file(file_data, 'badfile.exe'))
        with responses.RequestsMock():
            # does not load prison list
            form = LocationFileUploadForm(request.POST, request.FILES, request=request)
            self.assertFalse(form.is_valid())

        self.assertEqual(
            form.errors['location_file'],
            ['Uploaded file must be a CSV']
        )

    def test_location_file_without_valid_rows(self):
        file_data, _ = generate_testable_location_data(length=0, extra_rows=[
            'A1234ZZ,Smith,John,2/9/1997,TRN',
            'A1235ZZ,Smith,Fred,2/9/1997,ZCH',
        ])

        request = self.make_request(get_csv_data_as_file(file_data))
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = LocationFileUploadForm(request.POST, request.FILES, request=request)
            self.assertFalse(form.is_valid())

        self.assertEqual(
            form.errors['location_file'],
            ['The uploaded report contains no valid prisoner locations']
        )

    @mock.patch('prisoner_location_admin.tasks.api_client')
    @override_settings(UPLOAD_REQUEST_PAGE_SIZE=10)
    def test_location_file_batch_upload(self, mock_api_client):
        self.setup_mock_get_authenticated_api_session(mock_api_client)

        file_data, expected_data = generate_testable_location_data(length=50)
        expected_calls = [
            expected_data[40:50],
            expected_data[30:40],
            expected_data[20:30],
            expected_data[10:20],
            expected_data[0:10]
        ]

        request = self.make_request(get_csv_data_as_file(file_data))

        with responses.RequestsMock() as rsps, silence_logger(level=logging.WARNING):
            mock_prison_response(rsps)
            form = LocationFileUploadForm(request.POST, request.FILES, request=request)
            self.assertTrue(form.is_valid())

            rsps.add(
                rsps.POST,
                api_url('/prisoner_locations/actions/delete_inactive/')
            )
            rsps.add(
                rsps.POST,
                api_url('/prisoner_locations/')
            )
            rsps.add(
                rsps.POST,
                api_url('/prisoner_locations/actions/delete_old/')
            )
            form.update_locations()

            for call in rsps.calls:
                if call.request.url == api_url('/prisoner_locations/'):
                    self.assertEqual(
                        json.loads(call.request.body.decode()),
                        expected_calls.pop()
                    )

        if expected_calls:
            self.fail('Not all location data was uploaded')

    @mock.patch('prisoner_location_admin.tasks.api_client')
    @override_settings(UPLOAD_REQUEST_PAGE_SIZE=50)
    def test_location_file_with_ignored_prisons(self, mock_api_client):
        self.setup_mock_get_authenticated_api_session(mock_api_client)

        file_data, expected_data = generate_testable_location_data(length=20, extra_rows=[
            'A1234ZZ,Smith,John,2/9/1997,TRN',
            'A1235ZZ,Smith,Fred,2/9/1997,ZCH',
        ])
        expected_calls = [expected_data]

        request = self.make_request(get_csv_data_as_file(file_data))

        with responses.RequestsMock() as rsps, silence_logger(level=logging.WARNING):
            mock_prison_response(rsps)
            form = LocationFileUploadForm(request.POST, request.FILES, request=request)
            self.assertTrue(form.is_valid())

            rsps.add(
                rsps.POST,
                api_url('/prisoner_locations/actions/delete_inactive/')
            )
            rsps.add(
                rsps.POST,
                api_url('/prisoner_locations/')
            )
            rsps.add(
                rsps.POST,
                api_url('/prisoner_locations/actions/delete_old/')
            )
            form.update_locations()

            for call in rsps.calls:
                if call.request.url == api_url('/prisoner_locations/'):
                    self.assertEqual(
                        json.loads(call.request.body.decode()),
                        expected_calls.pop()
                    )

        if expected_calls:
            self.fail('Not all location data was uploaded')
