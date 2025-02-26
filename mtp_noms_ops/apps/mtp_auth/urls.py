from django.urls import re_path

from .views import SignUpView


urlpatterns = [
    re_path(r'^sign-up/$', SignUpView.as_view(), name='sign-up'),
]
