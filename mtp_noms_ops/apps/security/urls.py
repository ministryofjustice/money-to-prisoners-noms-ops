from django.conf.urls import url

from . import required_permissions, views
from mtp_noms_ops.view_utils import user_test

security_test = user_test(required_permissions)

app_name = 'security'
urlpatterns = [
    url(r'^$', security_test(views.dashboard_view),
        name='dashboard'),

    url(r'^sender-grouped/$', security_test(views.SenderGroupedView.as_view()),
        name='sender_grouped'),
    url(r'^sender-grouped/credits/$', security_test(views.SenderGroupedView.as_view(listing_credits=True)),
        name='sender_grouped_credits'),
    url(r'^prisoner-grouped/$', security_test(views.PrisonerGroupedView.as_view()),
        name='prisoner_grouped'),
    url(r'^prisoner-grouped/credits/$', security_test(views.PrisonerGroupedView.as_view(listing_credits=True)),
        name='prisoner_grouped_credits'),
    url(r'^credits/$', security_test(views.CreditsView.as_view()),
        name='credits'),
]
