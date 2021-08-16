import textwrap

from mtp_common.notify.templates import NotifyTemplateRegistry


class NomsOpsNotifyTemplates(NotifyTemplateRegistry):
    """
    Templates that the security app in mtp-noms-ops expects to exist in GOV.UK Notify
    """
    templates = {
        'noms-ops-export': {
            'subject': 'Prisoner money intelligence – Exported data',
            'body': textwrap.dedent("""
                ((export_message))
                ((attachment))

                ((export_description))

                The spreadsheet was generated at ((generated_at)).
            """).strip(),
            'personalisation': [
                'export_message', 'export_description',
                'generated_at',
                'attachment',
            ],
        },
    }
