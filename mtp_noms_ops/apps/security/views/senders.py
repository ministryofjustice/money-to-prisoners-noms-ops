from django.core.urlresolvers import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

from security.forms.senders import SendersDetailForm, SendersForm, SendersFormV2
from security.utils import sender_profile_name
from security.views.base import SecurityView, SecurityDetailView


class SenderListView(SecurityView):
    """
    Legacy Sender search view

    TODO: delete after search V2 goes live.
    """
    title = _('Payment sources')
    form_template_name = 'security/forms/senders.html'
    template_name = 'security/senders.html'
    form_class = SendersForm
    object_list_context_key = 'senders'

    def url_for_single_result(self, sender):
        return reverse('security:sender_detail', kwargs={'sender_id': sender['id']})


class SenderListViewV2(SecurityView):
    """
    Sender list/search view V2.
    """
    title = _('Payment sources')
    form_class = SendersFormV2
    template_name = 'security/senders_list.html'
    search_results_view = 'security:sender_search_results'
    simple_search_view = 'security:sender_list'
    object_list_context_key = 'senders'
    object_name = _('payment source')
    object_name_plural = _('payment sources')

    def url_for_single_result(self, sender):
        return reverse('security:sender_detail', kwargs={'sender_id': sender['id']})


class SenderDetailView(SecurityDetailView):
    """
    Sender profile view
    """
    title = _('Payment source')
    list_title = SenderListView.title
    list_url = reverse_lazy('security:sender_list')
    template_name = 'security/sender.html'
    form_class = SendersDetailForm
    id_kwarg_name = 'sender_id'
    object_context_key = 'sender'

    def get_title_for_object(self, detail_object):
        return sender_profile_name(detail_object)
