from django.conf.urls import url

from . import required_permissions, views
from mtp_noms_ops.utils import user_test

security_test = user_test(required_permissions)

app_name = 'security'
urlpatterns = [
    url(r'^credits/$', security_test(views.CreditListView.as_view()),
        name='credit_list'),
    url(r'^credits/export/$', security_test(views.CreditExportView.as_view()),
        name='credits_export'),

    url(r'^senders/$', security_test(views.SenderListView.as_view()),
        name='sender_list'),
    url(r'^senders/(?P<sender_id>[0-9]+)/$', security_test(views.SenderDetailView.as_view()),
        name='sender_detail'),

    url(r'^prisoners/$', security_test(views.PrisonerListView.as_view()),
        name='prisoner_list'),
    url(r'^prisoners/(?P<prisoner_id>[0-9]+)/$', security_test(views.PrisonerDetailView.as_view()),
        name='prisoner_detail'),

    url(r'^review-credits/$', security_test(views.ReviewCreditsView.as_view()),
        name='review_credits'),
]
