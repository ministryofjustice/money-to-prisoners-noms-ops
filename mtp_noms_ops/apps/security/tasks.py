import csv
import io
from urllib.parse import urljoin
import zipfile

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader as template_loader
from django.utils.translation import gettext
from django.utils import timezone
from mtp_common.api import retrieve_all_pages
from mtp_common.auth.api_client import get_connection_with_session
from mtp_common.spooling import spoolable

from security.export import write_header, write_credits
from security.utils import parse_date_fields


def zip_credit_export(attachment_name, output):
    zip_data = io.BytesIO()
    with zipfile.ZipFile(zip_data, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zip_entry:
        zip_entry.writestr(attachment_name, output)
    return zip_data.getvalue()


@spoolable(body_params=('user', 'session', 'filters'))
def email_credit_csv(*, user, session, endpoint_path, filters, export_description,
                     attachment_name, zip_attachment=True):
    endpoint = get_connection_with_session(user, session)
    for attr in endpoint_path.split('/'):
        endpoint = getattr(endpoint, attr)
    generated_at = timezone.now()
    object_list = parse_date_fields(retrieve_all_pages(endpoint.get, **filters))

    with io.StringIO() as output:
        writer = csv.writer(output)
        write_header(writer)
        write_credits(writer, object_list)
        output = output.getvalue()

    if zip_attachment:
        output = zip_credit_export(attachment_name, output)
        attachment_name += '.zip'
        attachment_type = 'application/zip'
    else:
        attachment_type = 'text/csv'

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
