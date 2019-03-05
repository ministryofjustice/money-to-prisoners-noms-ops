from django.conf.urls import url
from django.contrib.auth.decorators import login_required

from . import views


app_name = 'settings'
urlpatterns = [
    url(
        r'^confirm-prisons/$',
        login_required(views.ConfirmPrisonsView.as_view()),
        name='confirm_prisons'
    ),
    url(
        r'^confirm-prisons/confirmation/$',
        login_required(views.ConfirmPrisonsConfirmationView.as_view()),
        name='confirm_prisons_confirmation'
    ),
]
