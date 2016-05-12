from django.conf.urls import url

from . import required_permissions, views
from permissions import login_required

urlpatterns = [
    url(r'^$', login_required(required_permissions)(views.LocationFileUploadView.as_view()),
        name='location_file_upload'),
]
