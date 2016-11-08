import random
import string
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.test import SimpleTestCase
from django.utils.crypto import get_random_string
from mtp_common.auth.test_utils import generate_tokens

from prisoner_location_admin import required_permissions

TEST_PRISONS = ['AGI', 'OGS', 'BBB']


class PrisonerLocationUploadTestCase(SimpleTestCase):

    @mock.patch('mtp_common.auth.backends.api_client')
    def login(self, mock_api_client):
        mock_api_client.authenticate.return_value = {
            'pk': 5,
            'token': generate_tokens(),
            'user_data': {
                'first_name': 'Sam',
                'last_name': 'Hall',
                'username': 'shall',
                'applications': ['noms-ops'],
                'permissions': required_permissions,
            }
        }

        response = self.client.post(
            reverse('login'),
            data={'username': 'shall', 'password': 'pass'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        return mock_api_client.authenticate.return_value


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


def generate_testable_location_data(length=20, extra_row=None):
    file_data = ['NOMS Number,Offender Surname,Offender Given Name 1,Date of Birth,Establishment Code']
    expected_data = []

    if extra_row:
        file_data.append(extra_row)

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

    file_data.append('Latest Business Data Available')
    file_data.append(random_dob()[1])

    return '\n'.join(file_data), expected_data
