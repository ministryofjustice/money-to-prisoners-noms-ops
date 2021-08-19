from django.template.defaultfilters import striptags
from django.utils import timezone
from django.utils.dateformat import format as format_date
from mtp_common.api import retrieve_all_pages_for_path
from mtp_common.auth.api_client import get_api_session_with_session
from mtp_common.spooling import spoolable
from mtp_common.tasks import send_email
from openpyxl.writer.excel import save_virtual_workbook

from security.export import ObjectListSerialiser
from security.utils import convert_date_fields


@spoolable(body_params=('user', 'session', 'filters'))
def email_export_xlsx(*, object_type, user, session, endpoint_path, filters, export_description):
    if object_type == 'credits':
        export_message = 'Click the link to download the credits you exported from ‘Prisoner money intelligence’.'
    elif object_type == 'disbursements':
        export_message = (
            'Click the link to download the bank transfer and cheque disbursements '
            'you exported from ‘Prisoner money intelligence’. '
            'You can’t see cash or postal orders here.'
        )

    elif object_type == 'senders':
        export_message = (
            'Click the link to download the list of payment sources you exported from ‘Prisoner money intelligence’.'
        )
    elif object_type == 'prisoners':
        export_message = (
            'Click the link to download the list of prisoners you exported from ‘Prisoner money intelligence’.'
        )
    else:
        raise NotImplementedError(f'Cannot export {object_type}')

    api_session = get_api_session_with_session(user, session)
    generated_at = timezone.now()
    object_list = convert_date_fields(
        retrieve_all_pages_for_path(api_session, endpoint_path, **filters)
    )

    serialiser = ObjectListSerialiser.serialiser_for(object_type)
    workbook = serialiser.make_workbook(object_list)
    attachment = save_virtual_workbook(workbook)

    send_email(
        template_name='noms-ops-export',
        to=user.email,
        personalisation={
            'export_message': export_message,
            'export_description': striptags(export_description),
            'generated_at': format_date(generated_at, 'd/m/Y H:I'),
            'attachment': attachment,
        },
        staff_email=True,
    )
