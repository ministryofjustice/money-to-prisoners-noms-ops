import random
import string

from django.core.files.uploadedfile import SimpleUploadedFile

TEST_PRISONS = ['048', '067', '054']


def get_csv_data_as_file(data):
    return SimpleUploadedFile(
        'example.csv',
        bytes(data, 'utf-8'),
        content_type='text/csv'
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
        num = random_prisoner_num()
        dob = random_dob()
        prison = random.choice(TEST_PRISONS)

        file_data.append('%s,%s,%s' % (num, dob, prison))
        expected_data.append({
            'prisoner_number': num,
            'prisoner_dob': dob,
            'prison': prison
        })

    return '\n'.join(file_data), expected_data
