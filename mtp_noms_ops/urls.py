from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.i18n import i18n_patterns
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.views.generic import RedirectView
from moj_irat.views import HealthcheckView, PingJsonView
from mtp_common.auth import views as auth_views
from mtp_common.auth.api_client import get_connection
from mtp_common.auth.exceptions import Unauthorized

from security.searches import get_saved_searches, populate_new_result_count


def dashboard_view(request):
    if not (request.can_access_prisoner_location or request.can_access_security):
        raise Unauthorized()  # middleware causes user to be logged-out
    if request.can_access_prisoner_location and not (
            request.can_access_security or request.can_access_user_management):
        return redirect(reverse_lazy('location_file_upload'))
    client = get_connection(request)
    return render(request, 'dashboard.html', {
        'start_page_url': settings.START_PAGE_URL,
        'saved_searches': [
            populate_new_result_count(client, search)
            for search in get_saved_searches(client)
        ]
    })


urlpatterns = i18n_patterns(
    url(r'^$', dashboard_view, name='dashboard'),
    url(r'^prisoner-location/', include('prisoner_location_admin.urls')),
    url(r'^security/', include('security.urls', namespace='security')),
    url(r'^feedback/', include('feedback.urls')),

    url(
        r'^login/$', auth_views.login, {
            'template_name': 'mtp_auth/login.html',
        }, name='login'),
    url(
        r'^logout/$', auth_views.logout, {
            'template_name': 'mtp_auth/login.html',
            'next_page': reverse_lazy('login'),
        }, name='logout'
    ),
    url(
        r'^password_change/$', auth_views.password_change, {
            'template_name': 'mtp_common/auth/password_change.html',
            'cancel_url': reverse_lazy(settings.LOGIN_REDIRECT_URL),
        }, name='password_change'
    ),
    url(
        r'^password_change_done/$', auth_views.password_change_done, {
            'template_name': 'mtp_common/auth/password_change_done.html',
            'cancel_url': reverse_lazy(settings.LOGIN_REDIRECT_URL),
        }, name='password_change_done'
    ),
    url(
        r'^reset-password/$', auth_views.reset_password, {
            'template_name': 'mtp_common/auth/reset-password.html',
            'cancel_url': reverse_lazy(settings.LOGIN_REDIRECT_URL),
        }, name='reset_password'
    ),
    url(
        r'^reset-password-done/$', auth_views.reset_password_done, {
            'template_name': 'mtp_common/auth/reset-password-done.html',
            'cancel_url': reverse_lazy(settings.LOGIN_REDIRECT_URL),
        }, name='reset_password_done'
    ),

    url(r'^', include('mtp_common.user_admin.urls')),

    url(r'^404.html$', lambda request: TemplateResponse(request, 'mtp_common/errors/404.html', status=404)),
    url(r'^500.html$', lambda request: TemplateResponse(request, 'mtp_common/errors/500.html', status=500)),
)

urlpatterns += [
    url(r'^ping.json$', PingJsonView.as_view(
        build_date_key='APP_BUILD_DATE',
        commit_id_key='APP_GIT_COMMIT',
        version_number_key='APP_BUILD_TAG',
    ), name='ping_json'),
    url(r'^healthcheck.json$', HealthcheckView.as_view(), name='healthcheck_json'),

    url(r'^favicon.ico$', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon.ico', permanent=True)),
    url(r'^robots.txt$', lambda request: HttpResponse('User-agent: *\nDisallow: /', content_type='text/plain')),
]

handler404 = 'mtp_common.views.page_not_found'
handler500 = 'mtp_common.views.server_error'
handler400 = 'mtp_common.views.bad_request'
