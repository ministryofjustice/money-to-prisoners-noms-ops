from django.contrib.auth.decorators import login_required
from django.conf.urls import url
from django.views.generic.base import TemplateView

from . import views

urlpatterns = [
    url(r'^$', login_required(views.LocationFileUploadView.as_view()),
        name='location_file_upload'),
]
