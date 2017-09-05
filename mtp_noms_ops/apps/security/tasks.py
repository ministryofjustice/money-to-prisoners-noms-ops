from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader as template_loader
from django.utils.translation import gettext
from django.utils import timezone
from mtp_common.api import retrieve_all_pages_for_path
from mtp_common.auth.api_client import get_api_session_with_session
from mtp_common.spooling import spoolable
from openpyxl import Workbook
from openpyxl.writer.excel import save_virtual_workbook

from security.export import write_header, write_credits
from security.utils import parse_date_fields


@spoolable(body_params=('user', 'session', 'filters'))
def email_credit_xlsx(*, user, session, endpoint_path, filters, export_description,
                      attachment_name):
    api_session = get_api_session_with_session(user, session)
    generated_at = timezone.now()
    object_list = parse_date_fields(
        retrieve_all_pages_for_path(api_session, endpoint_path, **filters)
    )

    wb = Workbook()
    write_header(wb)
    write_credits(wb, object_list)
    output = save_virtual_workbook(wb)

    attachment_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    template_context = {
        'static_url': urljoin(settings.SITE_URL, settings.STATIC_URL),
        'export_description': export_description,
        'generated_at': generated_at,
    }
    subject = '%s - %s' % (gettext('Prisoner money intelligence'), gettext('Credits exported'))
    from_address = getattr(settings, 'MAILGUN_FROM_ADDRESS', '') or settings.DEFAULT_FROM_EMAIL
    text_body = template_loader.get_template('security/email/export-credits.txt').render(template_context)
    html_body = template_loader.get_template('security/email/export-credits.html').render(template_context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body.strip('\n'),
        from_email=from_address,
        to=[user.email]
    )
    email.attach_alternative(html_body, mimetype='text/html')
    email.attach(attachment_name, output, mimetype=attachment_type)
    email.send()
