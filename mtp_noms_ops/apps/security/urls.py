from django.conf import settings
from django.conf.urls import url
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from mtp_common.auth.api_client import get_api_session

from mtp_noms_ops.utils import user_test
from security import required_permissions, views, SEARCH_V2_FLAG
from security.searches import get_saved_searches, populate_new_result_counts
from security.utils import can_skip_confirming_prisons, is_hmpps_employee


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
    })


def search_v2_view_redirect(view, search_v2_redirect_view_name=None, legacy_search_redirect_view_name=None):
    """
    Redirects to `search_v2_redirect_view_name` if not None and the user has the SEARCH_V2_FLAG on
        (meaning `view` is legacy search and shouldn't be served).
    Redirects to `legacy_search_redirect_view_name` if not None and the user doesn't have the SEARCH_V2_FLAG on
        (meaning `view` is search v2 but user can't access it).
    """
    def inner(request, *args, **kwargs):
        if SEARCH_V2_FLAG in request.user.user_data['flags']:
            if search_v2_redirect_view_name:
                return redirect(search_v2_redirect_view_name)
        else:
            if legacy_search_redirect_view_name:
                return redirect(legacy_search_redirect_view_name)
        return view(request, *args, **kwargs)
    return inner


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
            search_v2_view_redirect(
                views.CreditListViewV2.as_view(
                    view_type=views.ViewType.simple_search_form,
                ),
                legacy_search_redirect_view_name='security:credit_list_legacy',
            ),
        ),
        name='credit_list',
    ),
    url(
        r'^credits/advanced-search/$',
        security_test(
            search_v2_view_redirect(
                views.CreditListViewV2.as_view(
                    view_type=views.ViewType.advanced_search_form,
                ),
                legacy_search_redirect_view_name='security:credit_list_legacy',
            ),
        ),
        name='credit_advanced_search',
    ),
    url(
        r'^credits/search-results/$',
        security_test(
            search_v2_view_redirect(
                views.CreditListViewV2.as_view(
                    view_type=views.ViewType.search_results,
                ),
                legacy_search_redirect_view_name='security:credit_list_legacy',
            ),
        ),
        name='credit_search_results',
    ),
    url(
        r'^credits/export/$',
        security_test(
            search_v2_view_redirect(
                views.CreditListViewV2.as_view(
                    view_type=views.ViewType.export_download,
                ),
                legacy_search_redirect_view_name='security:credit_list_legacy',
            ),
        ),
        name='credit_export',
    ),
    url(
        r'^credits/email-export/$',
        security_test(
            search_v2_view_redirect(
                views.CreditListViewV2.as_view(
                    view_type=views.ViewType.export_email,
                ),
                legacy_search_redirect_view_name='security:credit_list_legacy',
            ),
        ),
        name='credit_email_export',
    ),
    url(
        r'^security/credits/(?P<credit_id>\d+)/$',
        security_test(views.CreditDetailView.as_view()),
        name='credit_detail',
    ),


    # TODO: delete _legacy views after search V2 goes live.
    url(
        r'^security/credits/$',
        security_test(
            search_v2_view_redirect(
                views.CreditListView.as_view(),
                search_v2_redirect_view_name='security:credit_list',
            )
        ),
        name='credit_list_legacy',
    ),
    url(
        r'^security/credits/export/$',
        security_test(
            search_v2_view_redirect(
                views.CreditListView.as_view(
                    view_type=views.ViewType.export_download,
                ),
                search_v2_redirect_view_name='security:credit_list',
            ),
        ),
        name='credit_export_legacy',
    ),
    url(
        r'^security/credits/email-export/$',
        security_test(
            search_v2_view_redirect(
                views.CreditListView.as_view(
                    view_type=views.ViewType.export_email,
                ),
                search_v2_redirect_view_name='security:credit_list',
            ),
        ),
        name='credit_email_export_legacy',
    ),

    # senders
    url(
        r'^senders/$',
        security_test(
            search_v2_view_redirect(
                views.SenderListViewV2.as_view(
                    view_type=views.ViewType.simple_search_form,
                ),
                legacy_search_redirect_view_name='security:sender_list_legacy',
            ),
        ),
        name='sender_list',
    ),
    url(
        r'^senders/advanced-search/$',
        security_test(
            search_v2_view_redirect(
                views.SenderListViewV2.as_view(
                    view_type=views.ViewType.advanced_search_form,
                ),
                legacy_search_redirect_view_name='security:sender_list_legacy',
            ),
        ),
        name='sender_advanced_search',
    ),
    url(
        r'^senders/search-results/$',
        security_test(
            search_v2_view_redirect(
                views.SenderListViewV2.as_view(
                    view_type=views.ViewType.search_results,
                ),
                legacy_search_redirect_view_name='security:sender_list_legacy',
            ),
        ),
        name='sender_search_results',
    ),
    url(
        r'^senders/export/$',
        security_test(
            search_v2_view_redirect(
                views.SenderListViewV2.as_view(
                    view_type=views.ViewType.export_download,
                ),
                legacy_search_redirect_view_name='security:sender_list_legacy',
            ),
        ),
        name='sender_export',
    ),
    url(
        r'^senders/email-export/$',
        security_test(
            search_v2_view_redirect(
                views.SenderListViewV2.as_view(
                    view_type=views.ViewType.export_email,
                ),
                legacy_search_redirect_view_name='security:sender_list_legacy',
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


    # TODO: delete _legacy views after search V2 goes live.
    url(
        r'^security/senders/$',
        security_test(
            search_v2_view_redirect(
                views.SenderListView.as_view(),
                search_v2_redirect_view_name='security:sender_list',
            ),
        ),
        name='sender_list_legacy',
    ),
    url(
        r'^security/senders/export/$',
        security_test(
            search_v2_view_redirect(
                views.SenderListView.as_view(
                    view_type=views.ViewType.export_download,
                ),
                search_v2_redirect_view_name='security:sender_list',
            ),
        ),
        name='sender_export_legacy',
    ),
    url(
        r'^security/senders/email-export/$',
        security_test(
            search_v2_view_redirect(
                views.SenderListView.as_view(
                    view_type=views.ViewType.export_email,
                ),
                search_v2_redirect_view_name='security:sender_list',
            ),
        ),
        name='sender_email_export_legacy',
    ),

    # prisoners
    url(
        r'^prisoners/$',
        security_test(
            search_v2_view_redirect(
                views.PrisonerListViewV2.as_view(
                    view_type=views.ViewType.simple_search_form,
                ),
                legacy_search_redirect_view_name='security:prisoner_list_legacy',
            ),
        ),
        name='prisoner_list',
    ),
    url(
        r'^prisoners/advanced-search/$',
        security_test(
            search_v2_view_redirect(
                views.PrisonerListViewV2.as_view(
                    view_type=views.ViewType.advanced_search_form,
                ),
                legacy_search_redirect_view_name='security:prisoner_list_legacy',
            ),
        ),
        name='prisoner_advanced_search',
    ),
    url(
        r'^prisoners/search-results/$',
        security_test(
            search_v2_view_redirect(
                views.PrisonerListViewV2.as_view(
                    view_type=views.ViewType.search_results,
                ),
                legacy_search_redirect_view_name='security:prisoner_list_legacy',
            ),
        ),
        name='prisoner_search_results',
    ),
    url(
        r'^prisoners/export/$',
        security_test(
            search_v2_view_redirect(
                views.PrisonerListViewV2.as_view(
                    view_type=views.ViewType.export_download,
                ),
                legacy_search_redirect_view_name='security:prisoner_list_legacy',
            ),
        ),
        name='prisoner_export'
    ),
    url(
        r'^prisoners/email-export/$',
        security_test(
            search_v2_view_redirect(
                views.PrisonerListViewV2.as_view(
                    view_type=views.ViewType.export_email,
                ),
                legacy_search_redirect_view_name='security:prisoner_list_legacy',
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


    # TODO: delete _legacy views after search V2 goes live.
    url(
        r'^security/prisoners/$',
        security_test(
            search_v2_view_redirect(
                views.PrisonerListView.as_view(),
                search_v2_redirect_view_name='security:prisoner_list',
            ),
        ),
        name='prisoner_list_legacy',
    ),
    url(
        r'^security/prisoners/export/$',
        security_test(
            search_v2_view_redirect(
                views.PrisonerListView.as_view(
                    view_type=views.ViewType.export_download,
                ),
                search_v2_redirect_view_name='security:prisoner_list',
            ),
        ),
        name='prisoner_export_legacy'
    ),
    url(
        r'^security/prisoners/email-export/$',
        security_test(
            search_v2_view_redirect(
                views.PrisonerListView.as_view(
                    view_type=views.ViewType.export_email,
                ),
                search_v2_redirect_view_name='security:prisoner_list',
            ),
        ),
        name='prisoner_email_export_legacy',
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
            search_v2_view_redirect(
                views.DisbursementListViewV2.as_view(
                    view_type=views.ViewType.simple_search_form,
                ),
                legacy_search_redirect_view_name='security:disbursement_list_legacy',
            ),
        ),
        name='disbursement_list',
    ),
    url(
        r'^disbursements/advanced-search/$',
        security_test(
            search_v2_view_redirect(
                views.DisbursementListViewV2.as_view(
                    view_type=views.ViewType.advanced_search_form,
                ),
                legacy_search_redirect_view_name='security:disbursement_list_legacy',
            ),
        ),
        name='disbursement_advanced_search',
    ),
    url(
        r'^disbursements/search-results/$',
        security_test(
            search_v2_view_redirect(
                views.DisbursementListViewV2.as_view(
                    view_type=views.ViewType.search_results,
                ),
                legacy_search_redirect_view_name='security:disbursement_list_legacy',
            ),
        ),
        name='disbursement_search_results',
    ),
    url(
        r'^disbursements/export/$',
        security_test(
            search_v2_view_redirect(
                views.DisbursementListViewV2.as_view(
                    view_type=views.ViewType.export_download,
                ),
                legacy_search_redirect_view_name='security:disbursement_list_legacy',
            ),
        ),
        name='disbursement_export',
    ),
    url(
        r'^disbursements/email-export/$',
        security_test(
            search_v2_view_redirect(
                views.DisbursementListViewV2.as_view(
                    view_type=views.ViewType.export_email,
                ),
                legacy_search_redirect_view_name='security:disbursement_list_legacy',
            ),
        ),
        name='disbursement_email_export',
    ),
    url(
        r'^security/disbursements/(?P<disbursement_id>\d+)/$',
        security_test(views.DisbursementDetailView.as_view()),
        name='disbursement_detail',
    ),


    # TODO: delete _legacy views after search V2 goes live.
    url(
        r'^security/disbursements/$',
        security_test(
            search_v2_view_redirect(
                views.DisbursementListView.as_view(),
                search_v2_redirect_view_name='security:disbursement_list',
            ),
        ),
        name='disbursement_list_legacy',
    ),
    url(
        r'^security/disbursements/export/$',
        security_test(
            search_v2_view_redirect(
                views.DisbursementListView.as_view(
                    view_type=views.ViewType.export_download,
                ),
                search_v2_redirect_view_name='security:disbursement_list',
            ),
        ),
        name='disbursement_export_legacy',
    ),
    url(
        r'^security/disbursements/email-export/$',
        security_test(
            search_v2_view_redirect(
                views.DisbursementListView.as_view(
                    view_type=views.ViewType.export_email,
                ),
                search_v2_redirect_view_name='security:disbursement_list',
            ),
        ),
        name='disbursement_email_export_legacy',
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
]
