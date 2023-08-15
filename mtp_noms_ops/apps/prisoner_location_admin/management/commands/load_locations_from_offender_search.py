import logging
import typing

from django.conf import settings
from django.core.management import BaseCommand
from django.utils.functional import cached_property
from mtp_common.auth import api_client, urljoin, MojUser
from mtp_common.nomis import connector, request_retry
from mtp_common.stack import StackException, is_first_instance
import requests

from prisoner_location_admin.models import PrisonerLocation
from prisoner_location_admin.tasks import update_locations
from security.models import PrisonList

logger = logging.getLogger('mtp')


class Command(BaseCommand):
    """
    Loads prisoner locations from offender search api for all known prisons and submits them to mtp-api
    """
    help = __doc__.strip().splitlines()[0]

    def add_arguments(self, parser):
        parser.add_argument('--scheduled', action='store_true')

    def handle(self, **options):
        scheduled = options['scheduled']
        if scheduled:
            self.stdout.write('Prisoner location upload is not idempotent')
            try:
                should_continue = is_first_instance()
            except StackException:
                self.stdout.write('Cannot determine if running on first instance so upload will be skipped')
                return
            if not should_continue:
                self.stdout.write('Not running on first instance so upload will be skipped')
                return
            self.stdout.write('Running on first instance so upload will proceed')

        try:
            user = self.get_uploading_user()
            prison_ids = self.get_known_prison_ids()
            locations = self.search_for_offenders(prison_ids)

            if locations:
                self.stdout.write('Scheduling prisoner locations for upload')
                update_locations(user=user, locations=locations)
            else:
                self.stdout.write('Not scheduling prisoner locations for upload')
        except Exception as e:  # noqa: E722,B001
            # catch and report any exception to prevent infinite uwsgi spooler loop
            logger.exception('Prisoner locations not loaded automatically from offender search')
            if hasattr(e, 'content') and isinstance(e.content, bytes):
                logger.error(e.content.decode())

    @cached_property
    def session(self) -> api_client.MoJOAuth2Session:
        return api_client.get_authenticated_api_session(
            settings.LOCATION_UPLOADER_USERNAME,
            settings.LOCATION_UPLOADER_PASSWORD,
        )

    def get_uploading_user(self) -> MojUser:
        user_data = self.session.get(f'/users/{settings.LOCATION_UPLOADER_USERNAME}/').json()
        user = MojUser(user_data['pk'], None, user_data)

        self.stdout.write(f'Starting prisoner location update as {user.username}')
        return user

    def get_known_prison_ids(self) -> typing.List[str]:
        prison_list = PrisonList(self.session)
        prison_ids = [prison['nomis_id'] for prison in prison_list.prisons]

        self.stdout.write(f'{len(prison_ids)} prisons with active prisoner locations')
        return prison_ids

    def search_for_offenders(self, prison_ids: typing.List[str]) -> typing.List[PrisonerLocation]:
        locations: typing.List[PrisonerLocation] = []

        headers = connector.build_request_api_headers()
        for prison_id in prison_ids:
            self.stdout.write(f'Searching for offenders in {prison_id}…')
            page = 0
            while True:
                url = urljoin(
                    settings.HMPPS_OFFENDER_SEARCH_BASE_URL,
                    f'/prison/{prison_id}/prisoners?cellLocationPrefix=&size=500&page={page}&sort=prisonerNumber,ASC',
                    trailing_slash=False,
                )
                response: requests.Response = request_retry(
                    'get',
                    url,
                    retries=0,
                    session=None,
                    headers=headers,
                )
                response.raise_for_status()
                response: OffenderSearchPrisonerList = response.json()
                page_of_offenders = response['content']
                offender_count = response['totalElements']
                self.stdout.write(
                    f'  page {page} loaded {len(page_of_offenders)} offenders from a total of {offender_count:,}'
                )
                if page_of_offenders:
                    locations.extend(to_prisoner_location(offender) for offender in page_of_offenders)
                else:
                    break
                if response['last']:
                    break
                page += 1

        self.stdout.write(f'Found {len(locations):,} prisoner locations in total')
        return locations


class OffenderSearchPrisoner(typing.TypedDict):
    prisonId: str  # noqa: N815
    cellLocation: str  # noqa: N815
    prisonerNumber: str  # noqa: N815
    bookingId: str  # noqa: N815
    firstName: str  # noqa: N815
    middleNames: typing.Optional[str]  # noqa: N815
    lastName: str  # noqa: N815
    dateOfBirth: str  # noqa: N815


class OffenderSearchPrisonerList(typing.TypedDict):
    content: typing.List[OffenderSearchPrisoner]
    totalElements: int  # noqa: N815
    last: bool


def to_prisoner_location(offender: OffenderSearchPrisoner) -> PrisonerLocation:
    return PrisonerLocation(
        prisoner_number=offender['prisonerNumber'],
        prisoner_name=(offender['firstName'] + ' ' + offender['lastName']).strip(),
        # date of birth from offender search is currently in format accepted by mtp-api
        prisoner_dob=offender['dateOfBirth'],
        prison=offender['prisonId'],
    )
