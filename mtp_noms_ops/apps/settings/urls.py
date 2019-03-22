from django.conf.urls import url
from django.contrib.auth.decorators import login_required

from . import views


urlpatterns = [
    url(
        r'^$',
        login_required(views.NomsOpsSettingsView.as_view()),
        name='settings'
    ),
    url(
        r'^change-prisons/$',
        login_required(views.ChangePrisonsView.as_view()),
        name='change_prisons'
    ),
    url(
        r'^confirm-prisons/$',
        login_required(views.ConfirmPrisonsView.as_view()),
        name='confirm_prisons'
    ),
    url(
        r'^confirm-prisons/add-remove/$',
        login_required(views.AddOrRemovePrisonsView.as_view()),
        name='confirm_prisons_add_remove'
    ),
    url(
        r'^confirm-prisons/confirmation/$',
        login_required(views.ConfirmPrisonsConfirmationView.as_view()),
        name='confirm_prisons_confirmation'
    ),
]
