from django.conf import settings
from django.conf.urls import url
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from mtp_common.auth.api_client import get_api_session

from . import required_permissions, views
from .searches import get_saved_searches, populate_new_result_counts
from .utils import can_skip_confirming_prisons, is_hmpps_employee
from mtp_noms_ops.utils import user_test


def security_test(view):
    view = user_passes_test(
        can_skip_confirming_prisons,
        login_url='confirm_prisons'
    )(view)
    view = user_passes_test(
        is_hmpps_employee,
        login_url='security:hmpps_employee'
    )(view)
    view = user_test(required_permissions)(view)
    return view


def dashboard_view(request):
    session = get_api_session(request)
    return render(request, 'dashboard.html', {
        'start_page_url': settings.START_PAGE_URL,
        'saved_searches': populate_new_result_counts(session, get_saved_searches(session)),
        'in_disbursement_pilot': any(
            prison['nomis_id'] in settings.DISBURSEMENT_PRISONS
            for prison in request.user_prisons
        ),
    })


app_name = 'security'
urlpatterns = [
    url(r'^$', security_test(dashboard_view), name='dashboard'),
    url(r'^confirm-hmpps-employee/$', login_required(views.HMPPSEmployeeView.as_view()), name='hmpps_employee'),
    url(r'^not-employee/$', views.NotHMPPSEmployeeView.as_view(), name='not_hmpps_employee'),

    # credits
    url(r'^credits/$', security_test(views.CreditListView.as_view()),
        name='credit_list'),
    url(r'^credits/(?P<credit_id>\d+)/$', security_test(views.CreditDetailView.as_view()),
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

    # senders
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
    url(r'^senders/(?P<sender_id>\d+)/$', security_test(views.SenderDetailView.as_view()),
        name='sender_detail'),
    url(r'^senders/(?P<sender_id>\d+)/export/$',
        security_test(views.SenderDetailView.as_view(
            export_view='download',
            export_redirect_view='security:sender_detail',
        )),
        name='sender_detail_export'),
    url(r'^senders/(?P<sender_id>\d+)/email-export/$',
        security_test(views.SenderDetailView.as_view(
            export_view='email',
            export_redirect_view='security:sender_detail',
        )),
        name='sender_detail_email_export'),

    # prisoners
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
    url(r'^prisoners/(?P<prisoner_id>\d+)/$', security_test(views.PrisonerDetailView.as_view()),
        name='prisoner_detail'),
    url(r'^prisoners/(?P<prisoner_id>\d+)/export/$',
        security_test(views.PrisonerDetailView.as_view(
            export_view='download',
            export_redirect_view='security:prisoner_detail',
        )),
        name='prisoner_detail_export'),
    url(r'^prisoners/(?P<prisoner_id>\d+)/email-export/$',
        security_test(views.PrisonerDetailView.as_view(
            export_view='email',
            export_redirect_view='security:prisoner_detail',
        )),
        name='prisoner_detail_email_export'),
    url(r'^prisoners/(?P<prisoner_id>\d+)/disbursements/$',
        security_test(views.PrisonerDisbursementDetailView.as_view()),
        name='prisoner_disbursement_detail'),
    url(r'^prisoners/(?P<prisoner_id>\d+)/disbursements/export/$',
        security_test(views.PrisonerDisbursementDetailView.as_view(
            export_view='download',
            export_redirect_view='security:prisoner_disbursement_detail',
        )),
        name='prisoner_disbursement_detail_export'),
    url(r'^prisoners/(?P<prisoner_id>\d+)/disbursements/email-export/$',
        security_test(views.PrisonerDisbursementDetailView.as_view(
            export_view='email',
            export_redirect_view='security:prisoner_disbursement_detail',
        )),
        name='prisoner_disbursement_detail_email_export'),

    # async-loaded nomis info
    url(r'^prisoner_image/(?P<prisoner_number>[A-Za-z0-9]*)/$',
        security_test(views.prisoner_image_view),
        name='prisoner_image'),
    url(r'^prisoner_nomis_info/(?P<prisoner_number>[A-Za-z0-9]*)/$',
        security_test(views.prisoner_nomis_info_view),
        name='prisoner_nomis_info'),

    # disbursements
    url(r'^disbursements/$', security_test(views.DisbursementListView.as_view()),
        name='disbursement_list'),
    url(r'^disbursements/(?P<disbursement_id>\d+)/$', security_test(views.DisbursementDetailView.as_view()),
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

    # review credits
    url(r'^review-credits/$', security_test(views.ReviewCreditsView.as_view()),
        name='review_credits'),

    # notifications
    url(r'^notifications/$', security_test(views.NotificationListView.as_view()),
        name='notification_list_current'),
    url(r'^notifications/(?P<week_start>[0-9]{4}-[0-9]{2}-[0-9]{2})/$',
        security_test(views.NotificationListView.as_view()),
        name='notification_list'),
]
