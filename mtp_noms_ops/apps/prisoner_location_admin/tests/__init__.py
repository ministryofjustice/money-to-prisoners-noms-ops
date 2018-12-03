import random
import string
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.test import SimpleTestCase
from django.utils.crypto import get_random_string
from mtp_common.auth.api_client import MoJOAuth2Session
from mtp_common.auth.test_utils import generate_tokens

from prisoner_location_admin import required_permissions

TEST_PRISONS = ['IXB', 'INP']


class PrisonerLocationUploadTestCase(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.notifications_mock = mock.patch('mtp_common.templatetags.mtp_common.notifications_for_request',
                                             return_value=[])
        self.notifications_mock.start()
        self.disable_cache = mock.patch('security.models.cache')
        self.disable_cache.start().get.return_value = None

    def tearDown(self):
        self.notifications_mock.stop()
        self.disable_cache.stop()
        super().tearDown()

    @mock.patch('mtp_common.auth.backends.api_client')
    def login(self, mock_api_client):
        mock_api_client.authenticate.return_value = {
            'pk': 5,
            'token': generate_tokens(),
            'user_data': {
                'first_name': 'Sam',
                'last_name': 'Hall',
                'username': 'shall',
                'email': 'sam@mtp.local',
                'permissions': required_permissions,
                'prisons': [],
                'flags': [],
            }
        }

        response = self.client.post(
            reverse('login'),
            data={'username': 'shall', 'password': 'pass'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        return mock_api_client.authenticate.return_value

    def setup_mock_get_authenticated_api_session(self, mock_api_client):
        mock_session = MoJOAuth2Session()
        mock_session.token = generate_tokens()
        mock_api_client.get_authenticated_api_session.return_value = mock_session


def get_csv_data_as_file(data, filename='example.csv'):
    return SimpleUploadedFile(
        filename,
        bytes(data, 'utf-8'),
        content_type='text/csv'
    )


def random_prisoner_name():
    return (
        '%s%s' % (
            get_random_string(allowed_chars=string.ascii_uppercase, length=1),
            get_random_string(allowed_chars=string.ascii_lowercase, length=random.randint(3, 6))
        ),
        '%s%s' % (
            get_random_string(allowed_chars=string.ascii_uppercase, length=1),
            get_random_string(allowed_chars=string.ascii_lowercase, length=random.randint(3, 9)),
        )
    )


def random_prisoner_num():
    return '%s%s%s%s' % (
        random.choice(string.ascii_uppercase),
        random.randint(1000, 9999),
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_uppercase)
    )


def random_dob():
    date = {
        'day': random.randint(1, 28),
        'month': random.randint(1, 12),
        'year': random.randint(1920, 1997),
    }
    time_format = random.randint(0, 2)
    if time_format == 0:
        date['time'] = ' 00:00'
    elif time_format == 1:
        date['time'] = ' 0:00:00'
    elif time_format == 2:
        date['time'] = ''

    return (
        '%(year)s-%(month)02d-%(day)02d' % date,
        '%(day)s/%(month)s/%(year)s%(time)s' % date,
    )


def generate_testable_location_data(length=20, extra_rows=None, excel_csv=False):
    file_data = ['NOMS Number,Offender Surname,Offender Given Name 1,Date of Birth,Establishment Code']
    expected_data = []

    if extra_rows:
        file_data.extend(extra_rows)

    for _ in range(length):
        firstname, surname = random_prisoner_name()
        num = random_prisoner_num()
        expected_dob, file_dob = random_dob()
        prison = random.choice(TEST_PRISONS)

        file_data.append('%s,%s,%s,%s,%s' % (num, surname, firstname, file_dob, prison))
        expected_data.append({
            'prisoner_number': num,
            'prisoner_name': ' '.join([firstname, surname]),
            'prisoner_dob': expected_dob,
            'prison': prison
        })

    penultimate_line = 'Latest Business Data Available'
    ultimate_line = random_dob()[1]
    if excel_csv:
        penultimate_line += ',,,,'
        ultimate_line += ',,,,'

    file_data.append(penultimate_line)
    file_data.append(ultimate_line)

    return '\n'.join(file_data), expected_data
