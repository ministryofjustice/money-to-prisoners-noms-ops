from itertools import chain

from django.contrib.auth.decorators import login_required, permission_required
from django.core.urlresolvers import reverse_lazy

from prisoner_location_admin import required_permissions as prisoner_location_permissions
from security import required_permissions as security_permissions


class UserPermissionMiddleware:
    @classmethod
    def process_request(cls, request):
        request.can_access_prisoner_location = request.user.has_perms(prisoner_location_permissions)
        request.can_access_security = request.user.has_perms(security_permissions)


def user_test(permissions):
    def decorator(view):
        permission_test = permission_required(permissions,
                                              login_url=reverse_lazy('redirect_to_start'))
        return login_required(permission_test(view))

    return decorator


def make_page_range(page, page_count, end_padding=2, page_padding=2):
    if page_count < 7:
        return range(1, page_count + 1)
    pages = sorted(set(chain(
        range(1, end_padding + 2),
        range(page - page_padding, page + page_padding + 1),
        range(page_count - end_padding, page_count + 1),
    )))
    pages_with_ellipses = []
    last_page = 0
    for page in pages:
        if page < 1 or page > page_count:
            continue
        if last_page + 1 < page:
            pages_with_ellipses.append(None)
        pages_with_ellipses.append(page)
        last_page = page
    return pages_with_ellipses
