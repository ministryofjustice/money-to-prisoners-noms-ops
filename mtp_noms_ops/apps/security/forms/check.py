from security.forms.object_base import SecurityForm
from security.utils import convert_date_fields


class CheckListForm(SecurityForm):
    """
    List of security checks.
    """

    def get_api_request_params(self):
        """
        Gets pending checks only, for now.
        """
        params = super().get_api_request_params()
        params['status'] = 'pending'
        return params

    def get_object_list_endpoint_path(self):
        return '/security/checks/'

    def get_object_list(self):
        """
        Gets objects and converts datetimes found in them.
        """
        return convert_date_fields(super().get_object_list(), include_nested=True)
