from urllib.parse import urljoin

from anymail.message import AnymailMessage
from django.conf import settings
from django.template import loader as template_loader
from django.utils.translation import gettext
from django.utils import timezone
from mtp_common.api import retrieve_all_pages_for_path
from mtp_common.auth.api_client import get_api_session_with_session
from mtp_common.spooling import spoolable
from openpyxl import Workbook
from openpyxl.writer.excel import save_virtual_workbook

from security.export import write_objects
from security.utils import parse_date_fields


@spoolable(body_params=('user', 'session', 'filters'))
def email_export_xlsx(*, object_type, user, session, endpoint_path, filters, export_description,
                      attachment_name):
    if object_type == 'credits':
        export_message = gettext('Attached are the credits you exported from ‘%(service_name)s’.')
    elif object_type == 'disbursements':
        export_message = (
            gettext('Attached are the bank transfer and cheque disbursements you exported from ‘%(service_name)s’.') +
            ' ' +
            gettext('You can’t see cash or postal orders here.')
        )
    elif object_type == 'senders':
        export_message = gettext('Attached is a list of payment sources you exported from ‘%(service_name)s’.')
    elif object_type == 'prisoners':
        export_message = gettext('Attached is a list of prisoners you exported from ‘%(service_name)s’.')
    else:
        export_message = None

    api_session = get_api_session_with_session(user, session)
    generated_at = timezone.now()
    object_list = parse_date_fields(
        retrieve_all_pages_for_path(api_session, endpoint_path, **filters)
    )

    wb = Workbook(write_only=True)
    write_objects(wb, object_type, object_list)
    output = save_virtual_workbook(wb)

    attachment_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    template_context = {
        'static_url': urljoin(settings.SITE_URL, settings.STATIC_URL),
        'export_description': export_description,
        'generated_at': generated_at,
        'export_message': export_message % {
            'service_name': gettext('Prisoner money intelligence')
        }

    }
    subject = '%s - %s' % (gettext('Prisoner money intelligence'), gettext('Credits exported'))
    from_address = getattr(settings, 'MAILGUN_FROM_ADDRESS', '') or settings.DEFAULT_FROM_EMAIL
    text_body = template_loader.get_template('security/email/export.txt').render(template_context)
    html_body = template_loader.get_template('security/email/export.html').render(template_context)
    email = AnymailMessage(
        subject=subject,
        body=text_body.strip('\n'),
        from_email=from_address,
        to=[user.email],
        tags=['export'],
    )
    email.attach_alternative(html_body, mimetype='text/html')
    email.attach(attachment_name, output, mimetype=attachment_type)
    email.send()
