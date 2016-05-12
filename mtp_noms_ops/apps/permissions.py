from django.contrib.auth.decorators import user_passes_test
from django.core.urlresolvers import reverse
from django.shortcuts import redirect


def login_required(permissions):
    def check_login_and_permissions(user):
        if not user.is_authenticated():
            # if not logged in, show login page
            return False
        if not user.has_perms(permissions):
            # if logged in but lacking permission, redirect to home page negotiation view
            return redirect(reverse('redirect_to_start'))
        return True

    return user_passes_test(check_login_and_permissions)
