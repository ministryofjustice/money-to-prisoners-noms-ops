import json
import logging
import math
import os
import pickle

from django.conf import settings
from django.forms import ValidationError
from django.utils.translation import gettext, gettext_lazy as _
from mtp_common.auth import api_client
from mtp_common.email import send_email
from slumber.exceptions import HttpClientError
from smtplib import SMTPException

logger = logging.getLogger('mtp')

try:
    import uwsgi  # noqa
    from mtp_common.uwsgidecorators import spool

    @spool(pass_arguments=True)
    def schedule_locations_update(user, filename):
        with open(filename, 'rb') as f:
            locations = pickle.load(f)
        os.unlink(filename)
        update_locations(user, locations, async=True)
except ImportError as e:
    schedule_locations_update = None


def format_errors(error_list):
    output_list = []
    for i, error in enumerate(error_list):
        if error:
            field_errors = []
            for key in error:
                field_errors += error[key]
            output_list.append('Row %s: %s' % (i+1, ', '.join(field_errors)))
    return output_list


def update_locations(user, locations, async=False):
    client = api_client.get_authenticated_connection(
        settings.LOCATION_UPLOADER_USERNAME,
        settings.LOCATION_UPLOADER_PASSWORD
    )
    username = user.user_data.get('username', 'Unknown')
    user_description = user.get_full_name()
    if user_description:
        user_description += ' (%s)' % username
    else:
        user_description = username

    errors = []
    location_count = len(locations)
    try:
        client.prisoner_locations.actions.delete_inactive.post()
        for i in range(math.ceil(location_count/settings.UPLOAD_REQUEST_PAGE_SIZE)):
            client.prisoner_locations.post(
                locations[
                    i*settings.UPLOAD_REQUEST_PAGE_SIZE:
                    (i+1)*settings.UPLOAD_REQUEST_PAGE_SIZE
                ]
            )
        client.prisoner_locations.actions.delete_old.post()

        logger.info('%d prisoner locations updated successfully by %s' % (
            location_count,
            user_description,
        ), extra={
            'elk_fields': {
                '@fields.prisoner_location_count': location_count,
                '@fields.username': username,
            }
        })
        return location_count
    except HttpClientError as e:
        logger.exception('Prisoner locations update by %s failed!' % user_description)
        if e.content:
            try:
                errors += format_errors(json.loads(e.content.decode('utf-8')))
            except ValueError:
                errors.append(e.content)
    except Exception as e:
        logger.exception('Prisoner locations update by %s failed!' % user_description)

    if not errors:
        errors.append(_('An unknown error occurred uploading prisoner locations'))
    logger.error(errors)

    if async:
        send_task_failure_notification(user.email, {'errors': errors})
    else:
        raise ValidationError(errors)


def send_task_failure_notification(email, context):
    if not email:
        return False
    try:
        send_email(
            email, 'prisoner_location_admin/email/failure-notification.txt',
            gettext('Send money to a prisoner: prisoner location update failed'),
            context=context, html_template='prisoner_location_admin/email/failure-notification.html'
        )
        return True
    except SMTPException:
        logger.exception('Could not send location upload failure notification')
