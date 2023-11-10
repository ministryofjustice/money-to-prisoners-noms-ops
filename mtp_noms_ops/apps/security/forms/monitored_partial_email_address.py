from security.forms.check import SecurityFormWithMyListCount


class MonitoredPartialEmailAddressListForm(SecurityFormWithMyListCount):
    """
    List of monitored partial email addresses
    """

    def get_object_list_endpoint_path(self):
        return '/security/monitored-email-addresses/'
