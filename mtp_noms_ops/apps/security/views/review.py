from django.contrib import messages
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from security.forms.review import ReviewCreditsForm


class ReviewCreditsView(FormView):
    title = _('New credits check')
    form_class = ReviewCreditsForm
    template_name = 'security/review.html'
    success_url = reverse_lazy('security:review_credits')

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs['request'] = self.request
        return form_kwargs

    def form_valid(self, form):
        count = form.review()
        messages.add_message(
            self.request, messages.INFO,
            _('%(count)d credits have been marked as checked by security') % {'count': count}
        )
        return super().form_valid(form=form)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['credits'] = context_data['form'].credits
        return context_data

    def get_class_name(self):
        return self.__class__.__name__

    def get_used_request_params(self):
        return []
