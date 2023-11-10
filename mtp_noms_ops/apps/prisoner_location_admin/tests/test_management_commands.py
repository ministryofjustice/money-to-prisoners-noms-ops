import collections
import datetime
import json
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from mtp_common.auth import MojUser
from mtp_common.test_utils import silence_logger
import responses

from prisoner_location_admin.management.commands.load_locations_from_offender_search import (
    OffenderSearchPrisonerList, OffenderSearchPrisoner,
)
from prisoner_location_admin.tests import (
    setup_mock_get_authenticated_api_session,
    random_dob, random_prisoner_name, random_prisoner_num,
)
from security.tests import api_url
from security.tests.test_forms.test_search_forms import mock_prison_response


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
    HMPPS_AUTH_BASE_URL='https://hmpps-auth-dev.local',
    HMPPS_OFFENDER_SEARCH_BASE_URL='https://offender-search-dev.local',
)
class LoadLocationsFromOffenderSearchTestCase(SimpleTestCase):
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.is_first_instance')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.timezone')
    def test_runs_only_on_first_instance(self, mock_timezone, mock_is_first_instance, mock_update_locations):
        mock_is_first_instance.return_value = False

        with silence_logger(), responses.RequestsMock():
            call_command('load_locations_from_offender_search', scheduled=True)

        mock_timezone.now.assert_not_called()
        mock_update_locations.assert_not_called()

    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.is_first_instance')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.timezone')
    @override_settings(ENVIRONMENT='test')
    def test_does_not_run_outside_office_hours_on_test(
        self, mock_timezone, mock_is_first_instance, mock_update_locations,
    ):
        mock_is_first_instance.return_value = True
        mock_timezone.now.return_value = timezone.make_aware(
            datetime.datetime(2023, 10, 23, 7, 42)
        )

        with silence_logger(), responses.RequestsMock():
            call_command('load_locations_from_offender_search', scheduled=True)

        mock_timezone.now.assert_called_once()
        mock_update_locations.assert_not_called()

    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.is_first_instance')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.timezone')
    @override_settings(ENVIRONMENT='test')
    def test_runs_in_office_hours_on_test(
        self, mock_timezone, mock_is_first_instance, mock_update_locations, mock_api_client,
    ):
        mock_is_first_instance.return_value = True
        mock_timezone.now.return_value = timezone.make_aware(
            datetime.datetime(2023, 10, 23, 11, 42)
        )
        setup_mock_get_authenticated_api_session(mock_api_client)

        with silence_logger(), responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)
            mock_offender_search_response(rsps, 'IXB', count_per_page=1)
            mock_offender_search_response(rsps, 'INP', count_per_page=0)

            call_command('load_locations_from_offender_search', scheduled=True)

        mock_timezone.now.assert_called_once()
        mock_update_locations.assert_called_once()

    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.is_first_instance')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.timezone')
    @override_settings(ENVIRONMENT='prod')
    def test_runs_outside_office_hours_on_prod(
        self, mock_timezone, mock_is_first_instance, mock_update_locations, mock_api_client,
    ):
        mock_is_first_instance.return_value = True
        mock_timezone.now.return_value = timezone.make_aware(
            datetime.datetime(2023, 10, 23, 7, 42)
        )
        setup_mock_get_authenticated_api_session(mock_api_client)

        with silence_logger(), responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)
            mock_offender_search_response(rsps, 'IXB', count_per_page=1)
            mock_offender_search_response(rsps, 'INP', count_per_page=0)

            call_command('load_locations_from_offender_search', scheduled=True)

        mock_timezone.now.assert_not_called()
        mock_update_locations.assert_called_once()

    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.is_first_instance')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.timezone')
    @override_settings(ENVIRONMENT='prod')
    def test_runs_in_office_hours_on_prod(
        self, mock_timezone, mock_is_first_instance, mock_update_locations, mock_api_client,
    ):
        mock_is_first_instance.return_value = True
        mock_timezone.now.return_value = timezone.make_aware(
            datetime.datetime(2023, 10, 23, 11, 42)
        )
        setup_mock_get_authenticated_api_session(mock_api_client)

        with silence_logger(), responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)
            mock_offender_search_response(rsps, 'IXB', count_per_page=1)
            mock_offender_search_response(rsps, 'INP', count_per_page=0)

            call_command('load_locations_from_offender_search', scheduled=True)

        mock_timezone.now.assert_not_called()
        mock_update_locations.assert_called_once()

    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    def test_mtp_auth_failure_does_not_throw_exception(self, mock_update_locations):
        with silence_logger(), responses.RequestsMock():
            call_command('load_locations_from_offender_search')

        mock_update_locations.assert_not_called()

    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    def test_hmpps_auth_failure_does_not_throw_exception(self, mock_update_locations, mock_api_client):
        setup_mock_get_authenticated_api_session(mock_api_client)

        with silence_logger(), responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)

            call_command('load_locations_from_offender_search')

        mock_update_locations.assert_not_called()

    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    def test_offender_search_failure_does_not_throw_exception(self, mock_update_locations, mock_api_client):
        setup_mock_get_authenticated_api_session(mock_api_client)

        with silence_logger(), responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)

            call_command('load_locations_from_offender_search')

        mock_update_locations.assert_not_called()

    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    def test_no_offenders_found(self, mock_update_locations, mock_api_client):
        setup_mock_get_authenticated_api_session(mock_api_client)

        with responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)
            mock_offender_search_response(rsps, 'IXB', count_per_page=0)
            mock_offender_search_response(rsps, 'INP', count_per_page=0)

            call_command('load_locations_from_offender_search')

        mock_update_locations.assert_not_called()

    @mock.patch('prisoner_location_admin.tasks.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    def test_one_offender_found(self, mock_update_locations, mock_api_client_command, mock_api_client_task):
        setup_mock_get_authenticated_api_session(mock_api_client_command)
        setup_mock_get_authenticated_api_session(mock_api_client_task)

        with responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)
            mock_offender_search_response(rsps, 'IXB', count_per_page=1)
            mock_offender_search_response(rsps, 'INP', count_per_page=0)

            call_command('load_locations_from_offender_search')

        mock_update_locations.assert_called_once()
        update_locations_call = mock_update_locations.mock_calls[-1]
        user = update_locations_call.kwargs['user']
        self.assertIsInstance(user, MojUser)
        self.assertEqual(user.username, 'prisoner-location-admin')
        prisoner_locations = update_locations_call.kwargs['locations']
        self.assertEqual(len(prisoner_locations), 1)
        prisoner_location = prisoner_locations[0]
        self.assertTrue(all(
            prisoner_location.get(key)
            for key in ['prisoner_number', 'prisoner_name', 'prisoner_dob', 'prison']
        ))
        self.assertEqual(prisoner_location['prison'], 'IXB')

    @mock.patch('prisoner_location_admin.tasks.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    def test_two_offenders_found(self, mock_update_locations, mock_api_client_command, mock_api_client_task):
        setup_mock_get_authenticated_api_session(mock_api_client_command)
        setup_mock_get_authenticated_api_session(mock_api_client_task)

        with responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)
            mock_offender_search_response(rsps, 'IXB', count_per_page=1)
            mock_offender_search_response(rsps, 'INP', count_per_page=1)

            call_command('load_locations_from_offender_search')

        mock_update_locations.assert_called_once()
        update_locations_call = mock_update_locations.mock_calls[-1]
        prisoner_locations = update_locations_call.kwargs['locations']
        self.assertEqual(len(prisoner_locations), 2)
        prisoner_location_counts_by_prison = collections.defaultdict(int)
        for prisoner_location in prisoner_locations:
            prisoner_location_counts_by_prison[prisoner_location['prison']] += 1
        self.assertDictEqual(prisoner_location_counts_by_prison, dict(IXB=1, INP=1))

    @mock.patch('prisoner_location_admin.tasks.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.update_locations')
    def test_four_offenders_found(self, mock_update_locations, mock_api_client_command, mock_api_client_task):
        setup_mock_get_authenticated_api_session(mock_api_client_command)
        setup_mock_get_authenticated_api_session(mock_api_client_task)

        with responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)
            mock_offender_search_response(rsps, 'IXB', count_per_page=1, pages=2)
            mock_offender_search_response(rsps, 'INP', count_per_page=1, pages=2)

            call_command('load_locations_from_offender_search')

        mock_update_locations.assert_called_once()
        update_locations_call = mock_update_locations.mock_calls[-1]
        prisoner_locations = update_locations_call.kwargs['locations']
        self.assertEqual(len(prisoner_locations), 4)
        prisoner_location_counts_by_prison = collections.defaultdict(int)
        for prisoner_location in prisoner_locations:
            prisoner_location_counts_by_prison[prisoner_location['prison']] += 1
        self.assertDictEqual(prisoner_location_counts_by_prison, dict(IXB=2, INP=2))

    @mock.patch('prisoner_location_admin.tasks.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    def test_prisoner_locations_uploaded_to_api(self, mock_api_client_command, mock_api_client_task):
        setup_mock_get_authenticated_api_session(mock_api_client_command)
        setup_mock_get_authenticated_api_session(mock_api_client_task)

        with responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)
            mock_offender_search_response(rsps, 'IXB', count_per_page=2, pages=3)
            mock_offender_search_response(rsps, 'INP', count_per_page=2, pages=2)

            rsps.post(api_url('/prisoner_locations/actions/delete_inactive/'))
            rsps.post(api_url('/prisoner_locations/'))
            rsps.post(api_url('/prisoner_locations/actions/delete_old/'))

            call_command('load_locations_from_offender_search')

            for call in rsps.calls:
                if call.request.url == api_url('/prisoner_locations/'):
                    data = json.loads(call.request.body.decode())

        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 10)

    @mock.patch('prisoner_location_admin.tasks.api_client')
    @mock.patch('prisoner_location_admin.management.commands.load_locations_from_offender_search.api_client')
    def test_upload_failure_does_not_throw_exception(self, mock_api_client_command, mock_api_client_task):
        setup_mock_get_authenticated_api_session(mock_api_client_command)
        setup_mock_get_authenticated_api_session(mock_api_client_task)

        with silence_logger(), responses.RequestsMock() as rsps:
            mock_get_uploading_user(rsps)
            mock_prison_response(rsps)
            mock_hmpps_auth_token(rsps)
            mock_offender_search_response(rsps, 'IXB', count_per_page=1)
            mock_offender_search_response(rsps, 'INP', count_per_page=1)

            rsps.post(api_url('/prisoner_locations/actions/delete_inactive/'))
            rsps.post(
                api_url('/prisoner_locations/'),
                status=400,
                body='[{"prison": ["server error"]}]'.encode()
            )

            call_command('load_locations_from_offender_search')


def mock_get_uploading_user(rsps: responses.RequestsMock):
    rsps.get(api_url('/users/prisoner-location-admin/'), json=dict(
        pk=11,
        username='prisoner-location-admin',
        first_name='Prisoner Location', last_name='Admin',
        email='prisoner-location-uploader@localhost',
        roles=['prisoner-location-admin'], flags=[], prisons=[],
        permissions=['prison.add_prisonerlocation', 'prison.delete_prisonerlocation'],
        is_active=True, is_locked_out=False, user_admin=False,
    ))


def mock_hmpps_auth_token(rsps: responses.RequestsMock):
    rsps.post('https://hmpps-auth-dev.local/oauth/token', json=dict(access_token='TOKEN', expires_in=3600))


def mock_offender_search_response(rsps: responses.RequestsMock, prison_id: str, count_per_page: int, pages=1):
    for page in range(pages):
        rsps.get(
            f'https://offender-search-dev.local/prison/{prison_id}/prisoners'
            f'?cellLocationPrefix=&size=500&page={page}&sort=prisonerNumber,ASC',
            json=OffenderSearchPrisonerList(
                content=[
                    OffenderSearchPrisoner(
                        prisonId=prison_id, cellLocation=f'1-1-{index:03}',
                        prisonerNumber=random_prisoner_num(), bookingId=f'1{index:04}',
                        firstName=random_prisoner_name()[0], middleNames=None, lastName=random_prisoner_name()[1],
                        dateOfBirth=random_dob()[0],
                    )
                    for index in range(count_per_page)
                ],
                totalElements=count_per_page * pages,
                last=page == pages - 1,
            ),
            match_querystring=True,
        )
