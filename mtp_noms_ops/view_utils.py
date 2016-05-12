from django.contrib.auth.decorators import login_required, permission_required
from django.core.urlresolvers import reverse_lazy


def user_test(permissions):
    def decorator(view):
        permission_test = permission_required(permissions,
                                              login_url=reverse_lazy('redirect_to_start'))
        return login_required(permission_test(view))

    return decorator
