from django.conf import settings
from mtp_common.auth import urljoin


def api_url(path):
    return urljoin(settings.API_URL, path)
