from django.contrib import messages
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from security.export import export_as_csv
from security.forms import (
    SendersForm, PrisonersForm, CreditsForm, ReviewCreditsForm
)


class SecurityView(FormView):
    """
    Base view for retrieving security-related searches
    Allows form submission via GET (using page parameter as the flag)
    """
    title = NotImplemented
    help_template_name = NotImplemented
    template_name = NotImplemented
    form_template_name = NotImplemented

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs['request'] = self.request
        if 'page' in self.request.GET:
            form_kwargs['data'] = self.request.GET
        else:
            form_kwargs['initial'].update(self.request.GET.dict())
        return form_kwargs

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['breadcrumbs'] = [
            {'name': _('Home'), 'url': reverse('dashboard')},
            {'name': self.title}
        ]
        return context_data

    def get(self, request, *args, **kwargs):
        if 'page' in self.request.GET:
            return self.post(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)


class CreditListView(SecurityView):
    """
    Credit search view
    """
    title = _('Credits')
    help_template_name = 'security/credits-help.html'
    form_template_name = 'security/credits-form.html'
    template_name = 'security/credits.html'
    form_class = CreditsForm

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        context['credits'] = form.get_object_list()
        return render(self.request, self.template_name, context)


class SenderListView(SecurityView):
    """
    Sender search view
    """
    title = _('Senders')
    help_template_name = 'security/senders-help.html'
    form_template_name = 'security/senders-form.html'
    template_name = 'security/senders.html'
    form_class = SendersForm

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        context['senders'] = form.get_object_list()
        return render(self.request, self.template_name, context)


class PrisonerListView(SecurityView):
    """
    Prisoner search view
    """
    title = _('Prisoners')
    help_template_name = 'security/prisoners-help.html'
    form_template_name = 'security/prisoners-form.html'
    template_name = 'security/prisoners.html'
    form_class = PrisonersForm

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        context['prisoners'] = form.get_object_list()
        return render(self.request, self.template_name, context)


class CreditExportView(SecurityView):
    form_class = CreditsForm

    def form_valid(self, form):
        data = form.get_complete_object_list()
        csvdata = export_as_csv(data)
        response = HttpResponse(csvdata, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="export.csv"'
        return response

    def form_invalid(self, form):
        return redirect('?'.join(
            filter(lambda x: x, [reverse('security:credit_list'), form.query_string])
        ))

    def get(self, request, *args, **kwargs):
        if 'page' in self.request.GET:
            return self.post(request, *args, **kwargs)
        return redirect('?'.join(
            filter(lambda x: x, [reverse('security:credit_list'), request.GET.urlencode()])
        ))


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
            _('{count} credits have been marked as checked by security').format(count=count)
        )
        return super().form_valid(form=form)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['credits'] = context_data['form'].credits
        return context_data
