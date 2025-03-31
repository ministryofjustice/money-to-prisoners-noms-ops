from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import include, reverse, reverse_lazy, re_path
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_control
from django.views.generic import RedirectView
from django.views.i18n import JavaScriptCatalog
from moj_irat.views import HealthcheckView, PingJsonView
from mtp_common.analytics import genericised_pageview
from mtp_common.auth import views as auth_views
from mtp_common.auth.exceptions import Unauthorized
from mtp_common.metrics.views import metrics_view

from mtp_auth.views import AcceptRequestView
from user_admin.views import UserCreationView, UserUpdateView
from views import FAQView


def login_view(request):
    return auth_views.login(request, template_name='mtp_auth/login.html', extra_context={
        'start_page_url': settings.START_PAGE_URL,
        'google_analytics_pageview': genericised_pageview(request, _('Sign in')),
    })


def root_view(request):
    if not (request.can_access_prisoner_location or request.can_access_security):
        raise Unauthorized()  # middleware causes user to be logged-out
    if request.can_access_prisoner_location and not request.can_access_security:
        return redirect(reverse('location_file_upload'))
    return redirect(reverse('security:dashboard'))


# NB: API settings has certain Noms Ops URLs which will need to be updated
# if they change: settings, feedback, and notifications
urlpatterns = i18n_patterns(
    re_path(r'^$', root_view, name='root'),
    re_path(r'^prisoner-location/', include('prisoner_location_admin.urls')),
    re_path(r'^settings/', include('settings.urls')),

    re_path(r'^faq/', FAQView.as_view(), name='faq'),
    re_path(r'^feedback/', include('feedback.urls')),

    re_path(r'^', include('mtp_auth.urls')),

    re_path(r'^login/$', login_view, name='login'),
    re_path(
        r'^logout/$', auth_views.logout, {
            'template_name': 'mtp_auth/login.html',
            'next_page': reverse_lazy('login'),
        }, name='logout'
    ),
    re_path(
        r'^password_change/$', auth_views.password_change, {
            'template_name': 'mtp_common/auth/password_change.html',
            'cancel_url': reverse_lazy(settings.LOGIN_REDIRECT_URL),
        }, name='password_change'
    ),
    re_path(
        r'^create_password/$', auth_views.password_change_with_code, {
            'template_name': 'mtp_common/auth/password_change_with_code.html',
            'cancel_url': reverse_lazy(settings.LOGIN_REDIRECT_URL),
        }, name='password_change_with_code'
    ),
    re_path(
        r'^password_change_done/$', auth_views.password_change_done, {
            'template_name': 'mtp_common/auth/password_change_done.html',
            'cancel_url': reverse_lazy(settings.LOGIN_REDIRECT_URL),
        }, name='password_change_done'
    ),
    re_path(
        r'^reset-password/$', auth_views.reset_password, {
            'password_change_url': reverse_lazy('password_change_with_code'),
            'template_name': 'mtp_common/auth/reset-password.html',
            'cancel_url': reverse_lazy(settings.LOGIN_REDIRECT_URL),
        }, name='reset_password'
    ),
    re_path(
        r'^reset-password-done/$', auth_views.reset_password_done, {
            'template_name': 'mtp_common/auth/reset-password-done.html',
            'cancel_url': reverse_lazy(settings.LOGIN_REDIRECT_URL),
        }, name='reset_password_done'
    ),
    re_path(
        r'^email_change/$', auth_views.email_change, {
            'cancel_url': reverse_lazy('settings'),
        }, name='email_change'
    ),
    re_path(r'^security/', include('security.urls', namespace='security')),

    # Override mtp_common.user_admin's /users/new/ view
    re_path(r'^users/new/$', UserCreationView.as_view(), name='new-user'),
    # Override mtp_common.user_admin's /users/{ID}/edit/ view
    re_path(r'^users/(?P<username>[^/]+)/edit/$', UserUpdateView.as_view(), name='edit-user'),
    re_path(r'^', include('mtp_common.user_admin.urls')),
    re_path(
        r'^users/request/(?P<account_request>\d+)/accept/$',
        AcceptRequestView.as_view(),
        name='accept-request'
    ),

    re_path(r'^js-i18n.js$', cache_control(public=True, max_age=86400)(JavaScriptCatalog.as_view()), name='js-i18n'),

    re_path(r'^404.html$', lambda request: TemplateResponse(request, 'mtp_common/errors/404.html', status=404)),
    re_path(r'^500.html$', lambda request: TemplateResponse(request, 'mtp_common/errors/500.html', status=500)),
)

urlpatterns += [
    re_path(r'^ping.json$', PingJsonView.as_view(
        build_date_key='APP_BUILD_DATE',
        commit_id_key='APP_GIT_COMMIT',
        version_number_key='APP_BUILD_TAG',
    ), name='ping_json'),
    re_path(r'^healthcheck.json$', HealthcheckView.as_view(), name='healthcheck_json'),
    re_path(r'^metrics.txt$', metrics_view, name='prometheus_metrics'),

    re_path(r'^favicon.ico$', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon.ico', permanent=True)),
    re_path(r'^robots.txt$', lambda request: HttpResponse('User-agent: *\nDisallow: /', content_type='text/plain')),
    re_path(r'^\.well-known/security\.txt$', RedirectView.as_view(
        url='https://security-guidance.service.justice.gov.uk/.well-known/security.txt',
        permanent=True,
    )),
]

handler404 = 'mtp_common.views.page_not_found'
handler500 = 'mtp_common.views.server_error'
handler400 = 'mtp_common.views.bad_request'
