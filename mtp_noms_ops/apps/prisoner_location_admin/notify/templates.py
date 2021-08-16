import textwrap

from mtp_common.notify.templates import NotifyTemplateRegistry


class NomsOpsNotifyTemplates(NotifyTemplateRegistry):
    """
    Templates that the prisoner location app in mtp-noms-ops expects to exist in GOV.UK Notify
    """
    templates = {
        'noms-ops-locations-failed': {
            'subject': 'Prisoner money: prisoner location update failed',
            'body': textwrap.dedent("""
                The upload of the prisoner location file failed, with the following errors:
                ((errors))

                You may need to try uploading the prisoner location report again.

                If you are unsure what the problem might be, please contact us at ((feedback_url))
            """).strip(),
            'personalisation': [
                'errors', 'feedback_url',
            ],
        },
    }
