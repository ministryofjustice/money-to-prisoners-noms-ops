from django.utils.translation import gettext_lazy

from security.forms.check import CheckListForm
from security.views.object_base import SecurityView


class CheckListView(SecurityView):
    """
    View returning the checks in pending status.
    """
    title = gettext_lazy('Payments pending')
    template_name = 'security/checks_list.html'
    form_class = CheckListForm
