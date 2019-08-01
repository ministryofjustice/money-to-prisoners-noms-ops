from django.core.urlresolvers import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

from security.utils import NameSet
from security.forms.prisoners import (
    PrisonersDetailForm,
    PrisonersDisbursementDetailForm,
    PrisonersForm,
    PrisonersFormV2,
)
from security.views.base import SecurityView, SecurityDetailView


class PrisonerListView(SecurityView):
    """
    Legacy Prisoner search view

    TODO: delete after search V2 goes live.
    """
    title = _('Prisoners')
    form_template_name = 'security/forms/prisoners.html'
    template_name = 'security/prisoners.html'
    form_class = PrisonersForm
    object_list_context_key = 'prisoners'

    def url_for_single_result(self, prisoner):
        return reverse('security:prisoner_detail', kwargs={'prisoner_id': prisoner['id']})


class PrisonerListViewV2(SecurityView):
    """
    Prisoner list/search view V2.
    """
    title = _('Prisoners')
    form_class = PrisonersFormV2
    template_name = 'security/prisoners_list.html'
    search_results_view = 'security:prisoner_search_results'
    simple_search_view = 'security:prisoner_list'
    object_list_context_key = 'prisoners'
    object_name = _('prisoner')
    object_name_plural = _('prisoners')

    def url_for_single_result(self, prisoner):
        return reverse('security:prisoner_detail', kwargs={'prisoner_id': prisoner['id']})


class PrisonerDetailView(SecurityDetailView):
    """
    Prisoner profile view showing credit list
    """
    title = _('Prisoner')
    list_title = PrisonerListView.title
    list_url = reverse_lazy('security:prisoner_list')
    template_name = 'security/prisoner.html'
    form_class = PrisonersDetailForm
    id_kwarg_name = 'prisoner_id'
    object_context_key = 'prisoner'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        prisoner = context_data.get('prisoner', {})
        if prisoner:
            context_data['provided_names'] = NameSet(
                prisoner.get('provided_names', ()), strip_titles=True
            )
        return context_data

    def get_title_for_object(self, detail_object):
        title = ' '.join(detail_object.get(key, '') for key in ('prisoner_number', 'prisoner_name'))
        return title.strip() or _('Unknown prisoner')


class PrisonerDisbursementDetailView(PrisonerDetailView):
    """
    Prisoner profile view showing disbursement list
    """
    template_name = 'security/prisoner-disbursements.html'
    form_class = PrisonersDisbursementDetailForm
    object_list_context_key = 'disbursements'
