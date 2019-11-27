from django.conf import settings
from django.conf.urls import url
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.views.generic.base import RedirectView
from mtp_common.auth.api_client import get_api_session

from mtp_noms_ops.utils import user_test
from security import required_permissions, views
from security.searches import get_saved_searches, populate_new_result_counts
from security.utils import can_manage_security_checks, can_skip_confirming_prisons, is_hmpps_employee


def security_test(view, extra_tests=None):
    view = user_passes_test(
        can_skip_confirming_prisons,
        login_url='confirm_prisons',
    )(view)
    view = user_passes_test(
        is_hmpps_employee,
        login_url='security:hmpps_employee',
    )(view)

    for extra_test in (extra_tests or []):
        view = user_passes_test(
            extra_test,
            login_url='root',
        )(view)

    view = user_test(required_permissions)(view)
    return view


def fiu_security_test(view):
    return security_test(
        view,
        extra_tests=[can_manage_security_checks],
    )


def dashboard_view(request):
    session = get_api_session(request)
    return render(request, 'dashboard.html', {
        'start_page_url': settings.START_PAGE_URL,
        'saved_searches': populate_new_result_counts(session, get_saved_searches(session)),
    })


app_name = 'security'
urlpatterns = [
    url(r'^security/$', security_test(dashboard_view), name='dashboard'),
    url(
        r'^security/confirm-hmpps-employee/$',
        login_required(views.HMPPSEmployeeView.as_view()),
        name='hmpps_employee',
    ),
    url(r'^security/not-employee/$', views.NotHMPPSEmployeeView.as_view(), name='not_hmpps_employee'),

    # credits
    url(
        r'^credits/$',
        security_test(
            views.CreditListViewV2.as_view(
                view_type=views.ViewType.simple_search_form,
            ),
        ),
        name='credit_list',
    ),
    url(
        r'^credits/advanced-search/$',
        security_test(
            views.CreditListViewV2.as_view(
                view_type=views.ViewType.advanced_search_form,
            ),
        ),
        name='credit_advanced_search',
    ),
    url(
        r'^credits/search-results/$',
        security_test(
            views.CreditListViewV2.as_view(
                view_type=views.ViewType.search_results,
            ),
        ),
        name='credit_search_results',
    ),
    url(
        r'^credits/export/$',
        security_test(
            views.CreditListViewV2.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='credit_export',
    ),
    url(
        r'^credits/email-export/$',
        security_test(
            views.CreditListViewV2.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='credit_email_export',
    ),
    url(
        r'^security/credits/(?P<credit_id>\d+)/$',
        security_test(views.CreditDetailView.as_view()),
        name='credit_detail',
    ),

    # senders
    url(
        r'^senders/$',
        security_test(
            views.SenderListViewV2.as_view(
                view_type=views.ViewType.simple_search_form,
            ),
        ),
        name='sender_list',
    ),
    url(
        r'^senders/advanced-search/$',
        security_test(
            views.SenderListViewV2.as_view(
                view_type=views.ViewType.advanced_search_form,
            ),
        ),
        name='sender_advanced_search',
    ),
    url(
        r'^senders/search-results/$',
        security_test(
            views.SenderListViewV2.as_view(
                view_type=views.ViewType.search_results,
            ),
        ),
        name='sender_search_results',
    ),
    url(
        r'^senders/export/$',
        security_test(
            views.SenderListViewV2.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='sender_export',
    ),
    url(
        r'^senders/email-export/$',
        security_test(
            views.SenderListViewV2.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='sender_email_export',
    ),
    url(
        r'^security/senders/(?P<sender_id>\d+)/$',
        security_test(views.SenderDetailView.as_view()),
        name='sender_detail',
    ),
    url(
        r'^security/senders/(?P<sender_id>\d+)/export/$',
        security_test(
            views.SenderDetailView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='sender_detail_export',
    ),
    url(
        r'^security/senders/(?P<sender_id>\d+)/email-export/$',
        security_test(
            views.SenderDetailView.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='sender_detail_email_export',
    ),

    # prisoners
    url(
        r'^prisoners/$',
        security_test(
            views.PrisonerListViewV2.as_view(
                view_type=views.ViewType.simple_search_form,
            ),
        ),
        name='prisoner_list',
    ),
    url(
        r'^prisoners/advanced-search/$',
        security_test(
            views.PrisonerListViewV2.as_view(
                view_type=views.ViewType.advanced_search_form,
            ),
        ),
        name='prisoner_advanced_search',
    ),
    url(
        r'^prisoners/search-results/$',
        security_test(
            views.PrisonerListViewV2.as_view(
                view_type=views.ViewType.search_results,
            ),
        ),
        name='prisoner_search_results',
    ),
    url(
        r'^prisoners/export/$',
        security_test(
            views.PrisonerListViewV2.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='prisoner_export'
    ),
    url(
        r'^prisoners/email-export/$',
        security_test(
            views.PrisonerListViewV2.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='prisoner_email_export',
    ),
    url(
        r'^security/prisoners/(?P<prisoner_id>\d+)/$',
        security_test(views.PrisonerDetailView.as_view()),
        name='prisoner_detail',
    ),
    url(
        r'^security/prisoners/(?P<prisoner_id>\d+)/export/$',
        security_test(
            views.PrisonerDetailView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='prisoner_detail_export',
    ),
    url(
        r'^security/prisoners/(?P<prisoner_id>\d+)/email-export/$',
        security_test(
            views.PrisonerDetailView.as_view(
                view_type=views.ViewType.export_email,
            )
        ),
        name='prisoner_detail_email_export',
    ),
    url(
        r'^security/prisoners/(?P<prisoner_id>\d+)/disbursements/$',
        security_test(views.PrisonerDisbursementDetailView.as_view()),
        name='prisoner_disbursement_detail',
    ),
    url(
        r'^security/prisoners/(?P<prisoner_id>\d+)/disbursements/export/$',
        security_test(
            views.PrisonerDisbursementDetailView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='prisoner_disbursement_detail_export',
    ),
    url(
        r'^security/prisoners/(?P<prisoner_id>\d+)/disbursements/email-export/$',
        security_test(
            views.PrisonerDisbursementDetailView.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='prisoner_disbursement_detail_email_export',
    ),

    # async-loaded nomis info
    url(
        r'^security/prisoner_image/(?P<prisoner_number>[A-Za-z0-9]*)/$',
        security_test(views.prisoner_image_view),
        name='prisoner_image',
    ),
    url(
        r'^security/prisoner_nomis_info/(?P<prisoner_number>[A-Za-z0-9]*)/$',
        security_test(views.prisoner_nomis_info_view),
        name='prisoner_nomis_info',
    ),

    # disbursements
    url(
        r'^disbursements/$',
        security_test(
            views.DisbursementListViewV2.as_view(
                view_type=views.ViewType.simple_search_form,
            ),
        ),
        name='disbursement_list',
    ),
    url(
        r'^disbursements/advanced-search/$',
        security_test(
            views.DisbursementListViewV2.as_view(
                view_type=views.ViewType.advanced_search_form,
            ),
        ),
        name='disbursement_advanced_search',
    ),
    url(
        r'^disbursements/search-results/$',
        security_test(
            views.DisbursementListViewV2.as_view(
                view_type=views.ViewType.search_results,
            ),
        ),
        name='disbursement_search_results',
    ),
    url(
        r'^disbursements/export/$',
        security_test(
            views.DisbursementListViewV2.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='disbursement_export',
    ),
    url(
        r'^disbursements/email-export/$',
        security_test(
            views.DisbursementListViewV2.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='disbursement_email_export',
    ),
    url(
        r'^security/disbursements/(?P<disbursement_id>\d+)/$',
        security_test(views.DisbursementDetailView.as_view()),
        name='disbursement_detail',
    ),

    # review credits
    url(
        r'^security/review-credits/$',
        security_test(views.ReviewCreditsView.as_view()),
        name='review_credits',
    ),

    # notifications
    url(
        r'^security/notifications/$',
        security_test(views.NotificationListView.as_view()),
        name='notification_list',
    ),

    # checks
    url(
        r'^security/checks/$',
        fiu_security_test(views.CheckListView.as_view()),
        name='check_list',
    ),
    url(
        r'^security/checks/(?P<check_id>\d+)/$',
        fiu_security_test(views.AcceptCheckView.as_view()),
        name='accept_check',
    ),

    # legacy views, they redirect to their v2 and should be safe to be removed eventually
    url(
        r'^security/credits/$',
        security_test(
            RedirectView.as_view(pattern_name='security:credit_list'),
        ),
        name='credit_list_legacy',
    ),
    url(
        r'^security/disbursements/$',
        security_test(
            RedirectView.as_view(pattern_name='security:disbursement_list'),
        ),
        name='disbursement_list_legacy',
    ),
    url(
        r'^security/senders/$',
        security_test(
            RedirectView.as_view(pattern_name='security:sender_list'),
        ),
        name='sender_list_legacy',
    ),
    url(
        r'^security/prisoners/$',
        security_test(
            RedirectView.as_view(pattern_name='security:prisoner_list'),
        ),
        name='prisoner_list_legacy',
    ),
]
