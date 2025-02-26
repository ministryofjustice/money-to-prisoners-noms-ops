from django.urls import re_path

from mtp_noms_ops.utils import user_test
from prisoner_location_admin import required_permissions, views


urlpatterns = [
    re_path(r'^$', user_test(required_permissions)(views.LocationFileUploadView.as_view()),
        name='location_file_upload'),
]
