from django.conf.urls import url

from . import required_permissions, views
from permissions import login_required

urlpatterns = [
    url(r'^$', login_required(required_permissions)(views.SecurityDashboardView.as_view()),
        name='security_dashboard'),
]
