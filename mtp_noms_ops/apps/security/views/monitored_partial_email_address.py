from django.utils.translation import gettext_lazy as _

from security.forms.monitored_partial_email_address import MonitoredPartialEmailAddressListForm
from security.views.object_base import SecurityView


class MonitoredPartialEmailAddressListView(SecurityView):
    """
    View list of monitored partial email addresses
    """
    title = _('Monitored email addresses')
    template_name = 'security/monitored-email-address-list.html'
    form_class = MonitoredPartialEmailAddressListForm
