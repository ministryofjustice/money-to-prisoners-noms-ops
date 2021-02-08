from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.urls import reverse, reverse_lazy
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext_lazy as _

from prisoner_location_admin import required_permissions as prisoner_location_permissions
from security import required_permissions as security_permissions
from security.utils import can_manage_security_checks


class UserPermissionMiddleware(MiddlewareMixin):
    @classmethod
    def process_request(cls, request):
        request.user_prisons = request.user.user_data.get('prisons') or []
        request.can_access_prisoner_location = request.user.has_perms(prisoner_location_permissions)
        request.can_access_security = request.user.has_perms(security_permissions)
        request.can_access_user_management = request.user.has_perm('auth.change_user')
        request.can_pre_approve = request.user.is_authenticated and any(
            prison['pre_approval_required']
            for prison in request.user_prisons
        )
        request.can_manage_security_checks = can_manage_security_checks(request.user)


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


def user_test(permissions):
    def decorator(view):
        permission_test = permission_required(permissions, login_url=reverse_lazy(settings.LOGIN_REDIRECT_URL))
        return login_required(permission_test(view))

    return decorator
