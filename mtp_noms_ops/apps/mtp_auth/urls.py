from django.conf.urls import url

from .views import SignUpView


urlpatterns = [
    url(r'^sign-up/$', SignUpView.as_view(), name='sign-up'),
]
