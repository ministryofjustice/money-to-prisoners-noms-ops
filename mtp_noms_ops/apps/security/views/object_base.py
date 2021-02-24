from enum import Enum
from urllib.parse import unquote

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.utils.functional import cached_property
from django.utils.http import is_safe_url
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from mtp_common.analytics import genericised_pageview
from mtp_common.auth.api_client import get_api_session
from mtp_common.auth.exceptions import HttpNotFoundError
from requests.exceptions import RequestException

from security.context_processors import initial_params
from security.export import ObjectListXlsxResponse
from security.tasks import email_export_xlsx


SEARCH_FORM_SUBMITTED_INPUT_NAME = 'form_submitted'


class ViewType(Enum):
    """
    Enum for the different variants of views for a specific class of objects.
    """
    simple_search_form = 'simple_search_form'
    advanced_search_form = 'advanced_search_form'
    search_results = 'search_results'
    export_download = 'export_download'
    export_email = 'export_email'
    detail = 'detail'


class SimpleSecurityDetailView(TemplateView):
    """
    Base view for showing a single templated page without a form
    """
    title = NotImplemented
    template_name = NotImplemented
    object_context_key = NotImplemented
    list_title = NotImplemented
    list_url = NotImplemented

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.object = None

    @cached_property
    def session(self):
        return get_api_session(self.request)

    def get_object_request_params(self):
        raise NotImplementedError

    def get_object(self):
        try:
            return self.session.get(**self.get_object_request_params()).json()
        except HttpNotFoundError:
            raise Http404('%s not found' % self.object_context_key)
        except (RequestException, ValueError):
            messages.error(self.request, _('This service is currently unavailable'))
            return {}

    def get_context_data(self, **kwargs):
        self.object = self.get_object()

        context_data = super().get_context_data(**kwargs)
        context_data[self.object_context_key] = self.object

        list_url = self.get_list_url()

        context_data['breadcrumbs'] = self.get_breadcrumbs(list_url)
        return context_data

    def get_list_url(self):
        list_url = self.request.build_absolute_uri(str(self.list_url))
        referrer_url = self.request.META.get('HTTP_REFERER', '-')
        if referrer_url.split('?', 1)[0] == list_url:
            list_url = referrer_url
        return list_url


    def get_breadcrumbs(self, list_url):
        return [
            {'name': _('Home'), 'url': reverse('security:dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': self.title}
        ]

class SecurityView(FormView):
    """
    Base view for retrieving security-related searches
    Allows form submission via GET, i.e. form is always bound
    """
    title = NotImplemented
    advanced_search_template_name = NotImplemented
    object_list_context_key = NotImplemented
    view_type = None
    search_results_view = None
    simple_search_view = None
    advanced_search_view = None
    export_download_limit = settings.MAX_CREDITS_TO_DOWNLOAD
    export_email_limit = settings.MAX_CREDITS_TO_EMAIL
    object_name = None
    object_name_plural = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.redirect_on_single = False

    def get_template_names(self):
        """
        Return the advanced search template if the view type is 'adanced search' or the default
        template otherwise.
        """
        if self.view_type == ViewType.advanced_search_form:
            return self.advanced_search_template_name
        return self.template_name

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs['request'] = self.request
        request_data = self.request.GET.copy()
        if 'redirect-on-single' in request_data:
            self.redirect_on_single = True
        form_kwargs['data'] = request_data
        return form_kwargs

    def is_export_view_type(self):
        return self.view_type in (ViewType.export_download, ViewType.export_email)

    def form_valid(self, form):
        """
        If it's an export view, export and redirect to the referral view.
        If it's a simple form view, the form is valid and was submitted,
            redirect to the search results page.
        Else, render the template.
        """
        if self.is_export_view_type():
            attachment_name = 'exported-%s-%s.xlsx' % (
                self.object_list_context_key, date_format(timezone.now(), 'Y-m-d')
            )
            if self.view_type == ViewType.export_email:
                email_export_xlsx(
                    object_type=self.object_list_context_key,
                    user=self.request.user,
                    session=self.request.session,
                    endpoint_path=form.get_object_list_endpoint_path(),
                    filters=form.get_query_data(),
                    export_description=self.get_export_description(form),
                    attachment_name=attachment_name,
                )
                messages.info(
                    self.request,
                    _('The spreadsheet will be emailed to you at %(email)s') % {'email': self.request.user.email}
                )
                return self.redirect_to_referral_url()
            return ObjectListXlsxResponse(form.get_complete_object_list(),
                                          object_type=self.object_list_context_key,
                                          attachment_name=attachment_name)

        if (
            SEARCH_FORM_SUBMITTED_INPUT_NAME in self.request.GET
            and self.search_results_view
        ):
            search_results_url = f'{reverse(self.search_results_view)}?{form.query_string}'
            return redirect(search_results_url)

        if self.view_type != ViewType.advanced_search_form:
            object_list = form.get_object_list()
            context = self.get_context_data(form=form)
            if self.redirect_on_single and len(object_list) == 1 and hasattr(self, 'url_for_single_result'):
                return redirect(self.url_for_single_result(object_list[0]))
            context[self.object_list_context_key] = object_list
            # add objects as an alias for generic logic
            context['objects'] = object_list
        else:
            context = self.get_context_data(form=form)
        return render(self.request, self.get_template_names(), context)

    def form_invalid(self, form):
        """
        If the form is invalid and the view type is export or search results,
        it redirects back to the referral view so that the user can see and correct the errors.
        """
        if self.is_export_view_type() or self.view_type == ViewType.search_results:
            return self.redirect_to_referral_url()

        return super().form_invalid(form)

    def _get_breadcrumbs(self, **kwargs):
        prisons_param = initial_params(self.request).get('initial_params', '')
        if self.view_type == ViewType.advanced_search_form:
            return [
                {'name': _('Home'), 'url': reverse('security:dashboard')},
                {'name': self.title, 'url': f'{reverse(self.simple_search_view)}?{prisons_param}'},
                {'name': _('Advanced search')},
            ]

        if self.view_type == ViewType.search_results:
            if kwargs['form'].was_advanced_search_used():
                return [
                    {'name': _('Home'), 'url': reverse('security:dashboard')},
                    {'name': self.title, 'url': f'{reverse(self.simple_search_view)}?{prisons_param}'},
                    {
                        'name': _('Advanced search'),
                        'url': f'{reverse(self.advanced_search_view)}?{kwargs["form"].query_string}',
                    },
                    {'name': _('Advanced search results')},
                ]

            return [
                {'name': _('Home'), 'url': reverse('security:dashboard')},
                {'name': self.title, 'url': f'{reverse(self.simple_search_view)}?{prisons_param}'},
                {'name': _('Search results')},
            ]

        return [
            {'name': _('Home'), 'url': reverse('security:dashboard')},
            {'name': self.title},
        ]

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        return {
            **context_data,

            'breadcrumbs': self._get_breadcrumbs(**kwargs),
            'google_analytics_pageview': genericised_pageview(self.request, self.get_generic_title()),
            'search_form_submitted_input_name': SEARCH_FORM_SUBMITTED_INPUT_NAME,
        }

    def redirect_to_referral_url(self):
        """
        Returns an HttpResponseRedirect to the referer preserving the same kwargs and query string.
        """
        referer = self.request.META.get('HTTP_REFERER')
        if referer:
            referer = unquote(referer)  # HTTP_REFERER may be encoded.

        if not is_safe_url(
            url=referer,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            referer = '/'
        return redirect(referer)

    def get_export_description(self, form):
        return str(form.search_description['description'])

    def get_class_name(self):
        return self.__class__.__name__

    def get_generic_title(self):
        # not customised for specifc search or detail object
        return self.__class__.title

    def get_used_request_params(self):
        return sorted(
            param
            for param, value in self.request.GET.items()
            if value
        )

    get = FormView.post


class SecurityDetailView(SecurityView):
    """
    Base view for presenting a profile with associated credits
    Allows form submission via GET
    """
    list_title = NotImplemented
    list_url = NotImplemented
    id_kwarg_name = NotImplemented
    object_list_context_key = 'credits'
    object_context_key = NotImplemented
    view_type = ViewType.detail

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs['object_id'] = self.kwargs[self.id_kwarg_name]
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        detail_object = context_data['form'].get_object()
        if detail_object is None:
            raise Http404('Detail object not found')
        self.title = self.get_title_for_object(detail_object)
        list_url = self.request.build_absolute_uri(str(self.list_url))
        referrer_url = self.request.META.get('HTTP_REFERER', '-')
        if referrer_url.split('?', 1)[0] == list_url:
            list_url = referrer_url
        context_data[self.object_context_key] = detail_object

        context_data['breadcrumbs'] = [
            {'name': _('Home'), 'url': reverse('security:dashboard')},
            {'name': self.list_title, 'url': list_url},
            {'name': self.title}
        ]
        if hasattr(context_data['form'], 'check_and_update_saved_searches'):
            context_data['form'].check_and_update_saved_searches(str(self.title))
        return context_data

    def get_title_for_object(self, detail_object):
        raise NotImplementedError

    def get_export_description(self, form):
        detail_object = form.get_object()
        title = self.get_title_for_object(detail_object)
        return '%s: %s' % (title, super().get_export_description(form))
