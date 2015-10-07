from django.contrib.auth.decorators import login_required
from django.conf.urls import url
from django.views.generic.base import TemplateView

from . import views

urlpatterns = [
    url(
        r'^$', login_required(
            TemplateView.as_view(template_name='prisoner_location_admin/dashboard.html')
        ), name='dashboard'
    ),
    url(r'^upload/$', login_required(views.LocationFileUploadView.as_view()),
        name='location_file_upload'),
]
