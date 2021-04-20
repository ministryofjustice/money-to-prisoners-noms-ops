import json
import logging
import math
from urllib.parse import urljoin

from django.conf import settings
from django.forms import ValidationError
from django.urls import reverse
from django.utils.translation import activate, gettext, gettext_lazy as _
from mtp_common.auth import api_client
from mtp_common.auth.exceptions import HttpClientError
from mtp_common.spooling import Context, spoolable
from mtp_common.tasks import send_email

logger = logging.getLogger('mtp')


def format_errors(error_list):
    output_list = []
    for i, error in enumerate(error_list):
        if error:
            field_errors = []
            for key in error:
                field_errors += error[key]
            output_list.append('Row %s: %s' % (i + 1, ', '.join(field_errors)))
    return output_list


@spoolable(pre_condition=settings.ASYNC_LOCATION_UPLOAD, body_params=('user', 'locations'))
def update_locations(*, user, locations, context: Context):
    session = api_client.get_authenticated_api_session(
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
        session.post('/prisoner_locations/actions/delete_inactive/')
        pages = int(math.ceil(location_count / settings.UPLOAD_REQUEST_PAGE_SIZE))
        for page in range(pages):
            session.post(
                '/prisoner_locations/',
                json=locations[
                    page * settings.UPLOAD_REQUEST_PAGE_SIZE:
                    (page + 1) * settings.UPLOAD_REQUEST_PAGE_SIZE
                ]
            )
        session.post('/prisoner_locations/actions/delete_old/')

        logger.info('%d prisoner locations updated successfully by %s', (
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
        logger.exception('Prisoner locations update by %(user)s failed!', {'user': user_description})
        if hasattr(e, 'content') and e.content:
            try:
                errors += format_errors(json.loads(e.content.decode()))
            except ValueError:
                errors.append(e.content)
    except:  # noqa: E722,B001
        logger.exception('Prisoner locations update by %(user)s failed!', {'user': user_description})

    if not errors:
        errors.append(_('An unknown error occurred uploading prisoner locations'))
    logger.error('Prisoner locations update failed: %r', errors)

    if context.spooled:
        if user.email:
            send_task_failure_notification(user.email, {'errors': errors})
    else:
        raise ValidationError(errors)


def send_task_failure_notification(email, context):
    activate(settings.LANGUAGE_CODE)
    context['feedback_url'] = urljoin(settings.SITE_URL, reverse('submit_ticket'))
    send_email(
        email, 'prisoner_location_admin/email/failure-notification.txt',
        gettext('Prisoner money: prisoner location update failed'),
        context=context, html_template='prisoner_location_admin/email/failure-notification.html',
        anymail_tags=['locations-failed'],
    )
