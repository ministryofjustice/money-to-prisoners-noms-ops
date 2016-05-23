from django.contrib.auth.decorators import login_required, permission_required
from django.core.urlresolvers import reverse_lazy


def user_test(permissions):
    def decorator(view):
        permission_test = permission_required(permissions,
                                              login_url=reverse_lazy('redirect_to_start'))
        return login_required(permission_test(view))

    return decorator


def make_page_range(page, page_count):
    if page_count < 7:
        return range(1, page_count + 1)
    pages = sorted(set([1, 2] +
                       [page - 1, page, page + 1] +
                       [page_count - 1, page_count]))
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
