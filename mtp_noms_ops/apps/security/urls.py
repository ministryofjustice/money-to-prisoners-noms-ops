from django.contrib.auth.decorators import login_required
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', login_required(views.SecurityDashboardView.as_view()),
        name='security_dashboard'),
]
