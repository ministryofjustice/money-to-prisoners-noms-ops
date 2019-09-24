from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.urlresolvers import reverse, reverse_lazy
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext, gettext_lazy as _
from mtp_common.context_processors import govuk_localisation as inherited_localisation

from prisoner_location_admin import required_permissions as prisoner_location_permissions
from security import required_permissions as security_permissions, notifications_pilot_flag, SEARCH_V2_FLAG


class UserPermissionMiddleware:
    @classmethod
    def process_request(cls, request):
        request.user_prisons = request.user.user_data.get('prisons') or []
        request.can_access_prisoner_location = request.user.has_perms(prisoner_location_permissions)
        request.can_access_security = request.user.has_perms(security_permissions)
        request.can_access_user_management = request.user.has_perm('auth.change_user')
        request.can_access_notifications = (
            request.user.is_authenticated and notifications_pilot_flag in request.user.user_data.get('flags', [])
        )
        request.can_pre_approve = request.user.is_authenticated and any(
            prison['pre_approval_required']
            for prison in request.user_prisons
        )
        request.can_see_search_v2 = SEARCH_V2_FLAG in request.user.user_data.get('flags', [])


class SecurityMiddleware(MiddlewareMixin):
    def process_response(self, _, response):
        response['Referrer-Policy'] = 'same-origin'
        return response


def external_breadcrumbs(request):
    if not request.resolver_match:
        return {}
    url_name = '%s:%s' % (request.resolver_match.namespace, request.resolver_match.url_name)
    if url_name in (':submit_ticket', ':feedback_success'):
        section_title = _('Help and feedback')
    else:
        return {}
    return {
        'breadcrumbs': [
            {'name': _('Home'), 'url': reverse('security:dashboard')},
            {'name': section_title},
        ]
    }


def govuk_localisation(request):
    data = inherited_localisation(request)

    can_access_prisoner_location = getattr(request, 'can_access_prisoner_location', False)
    can_access_security = getattr(request, 'can_access_security', False)
    if can_access_prisoner_location and not can_access_security:
        app_title = _('Prisoner location admin')
    else:
        app_title = _('Prisoner money intelligence')
    data.update(
        app_title=app_title,
        homepage_url=data['home_url'],
        logo_link_title=gettext('Go to the homepage'),
        global_header_text=app_title,
    )
    return data


def user_test(permissions):
    def decorator(view):
        permission_test = permission_required(permissions, login_url=reverse_lazy(settings.LOGIN_REDIRECT_URL))
        return login_required(permission_test(view))

    return decorator
