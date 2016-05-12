from django.conf.urls import url

from . import required_permissions, views
from mtp_noms_ops.view_utils import user_test


urlpatterns = [
    url(r'^$', user_test(required_permissions)(views.LocationFileUploadView.as_view()),
        name='location_file_upload'),
]
