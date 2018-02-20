from django.conf.urls import url

from . import required_permissions, views
from mtp_noms_ops.utils import user_test

security_test = user_test(required_permissions)

app_name = 'security'
urlpatterns = [
    url(r'^credits/$', security_test(views.CreditListView.as_view()),
        name='credit_list'),
    url(r'^credits/(?P<credit_id>[0-9]+)/$', security_test(views.CreditDetailView.as_view()),
        name='credit_detail'),
    url(r'^credits/export/$',
        security_test(views.CreditListView.as_view(
            export_view='download',
            export_redirect_view='security:credit_list',
        )),
        name='credits_export'),
    url(r'^credits/email-export/$',
        security_test(views.CreditListView.as_view(
            export_view='email',
            export_redirect_view='security:credit_list',
        )),
        name='credits_email_export'),

    url(r'^senders/$', security_test(views.SenderListView.as_view()),
        name='sender_list'),
    url(r'^senders/export/$',
        security_test(views.SenderListView.as_view(
            export_view='download',
            export_redirect_view='security:sender_list',
        )),
        name='senders_export'),
    url(r'^senders/email-export/$',
        security_test(views.SenderListView.as_view(
            export_view='email',
            export_redirect_view='security:sender_list',
        )),
        name='senders_email_export'),
    url(r'^senders/(?P<sender_id>[0-9]+)/$', security_test(views.SenderDetailView.as_view()),
        name='sender_detail'),
    url(r'^senders/(?P<sender_id>[0-9]+)/export/$',
        security_test(views.SenderDetailView.as_view(
            export_view='download',
            export_redirect_view='security:sender_detail',
        )),
        name='sender_detail_export'),
    url(r'^senders/(?P<sender_id>[0-9]+)/email-export/$',
        security_test(views.SenderDetailView.as_view(
            export_view='email',
            export_redirect_view='security:sender_detail',
        )),
        name='sender_detail_email_export'),

    url(r'^prisoners/$', security_test(views.PrisonerListView.as_view()),
        name='prisoner_list'),
    url(r'^prisoners/export/$',
        security_test(views.PrisonerListView.as_view(
            export_view='download',
            export_redirect_view='security:prisoner_list',
        )),
        name='prisoners_export'),
    url(r'^prisoners/email-export/$',
        security_test(views.PrisonerListView.as_view(
            export_view='email',
            export_redirect_view='security:prisoner_list',
        )),
        name='prisoners_email_export'),
    url(r'^prisoners/(?P<prisoner_id>[0-9]+)/$', security_test(views.PrisonerDetailView.as_view()),
        name='prisoner_detail'),
    url(r'^prisoners/(?P<prisoner_id>[0-9]+)/export/$',
        security_test(views.PrisonerDetailView.as_view(
            export_view='download',
            export_redirect_view='security:prisoner_detail',
        )),
        name='prisoner_detail_export'),
    url(r'^prisoners/(?P<prisoner_id>[0-9]+)/email-export/$',
        security_test(views.PrisonerDetailView.as_view(
            export_view='email',
            export_redirect_view='security:prisoner_detail',
        )),
        name='prisoner_detail_email_export'),

    url(r'^prisoner_image/(?P<prisoner_number>[A-Za-z0-9]+)/$',
        security_test(views.prisoner_image_view),
        name='prisoner_image'),

    url(r'^disbursements/$', security_test(views.DisbursementListView.as_view()),
        name='disbursement_list'),
    url(r'^disbursements/(?P<disbursement_id>[0-9]+)/$', security_test(views.DisbursementDetailView.as_view()),
        name='disbursement_detail'),
    url(r'^disbursements/export/$',
        security_test(views.DisbursementListView.as_view(
            export_view='download',
            export_redirect_view='security:disbursement_list',
        )),
        name='disbursements_export'),
    url(r'^disbursements/email-export/$',
        security_test(views.DisbursementListView.as_view(
            export_view='email',
            export_redirect_view='security:disbursement_list',
        )),
        name='disbursements_email_export'),

    url(r'^review-credits/$', security_test(views.ReviewCreditsView.as_view()),
        name='review_credits'),
]
