from django.contrib.auth.decorators import login_required, permission_required
from django.core.urlresolvers import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

from prisoner_location_admin import required_permissions as prisoner_location_permissions
from security import required_permissions as security_permissions


class UserPermissionMiddleware:
    @classmethod
    def process_request(cls, request):
        request.can_access_prisoner_location = request.user.has_perms(prisoner_location_permissions)
        request.can_access_security = request.user.has_perms(security_permissions)
        request.can_access_user_management = request.user.has_perm('auth.change_user')
        request.can_pre_approve = any((
            prison['pre_approval_required']
            for prison in request.user.user_data.get('prisons', [])
        ))


def external_breadcrumbs(request):
    if not request.resolver_match:
        return {}
    url_name = '%s:%s' % (request.resolver_match.namespace, request.resolver_match.url_name)
    if url_name in (':submit_ticket', ':feedback_success'):
        section_title = _('Contact us')
    else:
        return {}
    return {
        'breadcrumbs': [
            {'name': _('Home'), 'url': reverse('redirect_to_start')},
            {'name': section_title}
        ]
    }


def user_test(permissions):
    def decorator(view):
        permission_test = permission_required(permissions,
                                              login_url=reverse_lazy('redirect_to_start'))
        return login_required(permission_test(view))

    return decorator
