import random
import string

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.crypto import get_random_string

TEST_PRISONS = ['048', '067', '054']


def get_csv_data_as_file(data, filename='example.csv'):
    return SimpleUploadedFile(
        filename,
        bytes(data, 'utf-8'),
        content_type='text/csv'
    )


def random_prisoner_name():
    return '%s%s %s%s' % (
        get_random_string(allowed_chars=string.ascii_uppercase, length=1),
        get_random_string(allowed_chars=string.ascii_lowercase, length=random.randint(3, 6)),
        get_random_string(allowed_chars=string.ascii_uppercase, length=1),
        get_random_string(allowed_chars=string.ascii_lowercase, length=random.randint(3, 9)),
    )


def random_prisoner_num():
    return '%s%s%s%s' % (
        random.choice(string.ascii_uppercase),
        random.randint(1000, 9999),
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_uppercase)
    )


def random_dob():
    return '%s-%s-%s' % (
        random.randint(1920, 1997),
        random.randint(1, 12),
        random.randint(1, 28)
    )


def generate_testable_location_data(length=20):
    file_data = []
    expected_data = []

    for _ in range(length):
        name = random_prisoner_name()
        num = random_prisoner_num()
        dob = random_dob()
        prison = random.choice(TEST_PRISONS)

        file_data.append('%s,%s,%s,%s' % (name, num, dob, prison))
        expected_data.append({
            'prisoner_name': name,
            'prisoner_number': num,
            'prisoner_dob': dob,
            'prison': prison
        })

    return '\n'.join(file_data), expected_data
