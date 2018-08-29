from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.urlresolvers import reverse, reverse_lazy
from django.utils.translation import gettext, gettext_lazy as _
from mtp_common.context_processors import govuk_localisation as inherited_localisation

from prisoner_location_admin import required_permissions as prisoner_location_permissions
from security import required_permissions as security_permissions


class UserPermissionMiddleware:
    @classmethod
    def process_request(cls, request):
        request.can_access_prisoner_location = request.user.has_perms(prisoner_location_permissions)
        request.can_access_security = request.user.has_perms(security_permissions)
        request.can_access_user_management = request.user.has_perm('auth.change_user')
        request.can_pre_approve = request.user.is_authenticated and any(
            prison['pre_approval_required']
            for prison in request.user.user_data.get('prisons', [])
        )
        request.disbursements_available = request.user.is_authenticated and any(
            prison['nomis_id'] in settings.DISBURSEMENT_PRISONS
            for prison in request.user.user_data.get('prisons', [])
        )


def external_breadcrumbs(request):
    if not request.resolver_match:
        return {}
    url_name = '%s:%s' % (request.resolver_match.namespace, request.resolver_match.url_name)
    if url_name in (':submit_ticket', ':feedback_success'):
        section_title = _('Get help')
    else:
        return {}
    return {
        'breadcrumbs': [
            {'name': _('Home'), 'url': reverse('dashboard')},
            {'name': section_title},
        ]
    }


def govuk_localisation(request):
    data = inherited_localisation(request)
    if request.can_access_prisoner_location and not request.can_access_security:
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
