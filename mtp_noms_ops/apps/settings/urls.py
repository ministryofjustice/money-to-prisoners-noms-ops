from django.contrib.auth.decorators import login_required
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(
        r'^$',
        login_required(views.NomsOpsSettingsView.as_view()),
        name='settings'
    ),
    re_path(
        r'^change-prisons/$',
        login_required(views.ChangePrisonsView.as_view()),
        name='change_prisons'
    ),
    re_path(
        r'^confirm-prisons/$',
        login_required(views.ConfirmPrisonsView.as_view()),
        name='confirm_prisons'
    ),
    re_path(
        r'^confirm-prisons/add-remove/$',
        login_required(views.AddOrRemovePrisonsView.as_view()),
        name='confirm_prisons_add_remove'
    ),
    re_path(
        r'^confirm-prisons/confirmation/$',
        login_required(views.ConfirmPrisonsConfirmationView.as_view()),
        name='confirm_prisons_confirmation'
    ),
    re_path(
        r'^job_information/$',
        login_required(views.JobInformationView.as_view()),
        name='job_information'
    )
]
