from django.conf import settings
from django.conf.urls import url
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
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


def search_v2_view_dispatcher(legacy_search_view, search_view_v2):
    """
    Dispatches to a version of the search depending on if the feature flag for
    that logged in user is set.
    """
    def inner(request, *args, **kwargs):
        if SEARCH_V2_FLAG in request.user.user_data['flags']:
            return search_view_v2(request, *args, **kwargs)
        return legacy_search_view(request, *args, **kwargs)
    return inner


app_name = 'security'
urlpatterns = [
    url(r'^$', security_test(dashboard_view), name='dashboard'),
    url(r'^confirm-hmpps-employee/$', login_required(views.HMPPSEmployeeView.as_view()), name='hmpps_employee'),
    url(r'^not-employee/$', views.NotHMPPSEmployeeView.as_view(), name='not_hmpps_employee'),

    # credits
    url(
        r'^credits/$',
        security_test(
            search_v2_view_dispatcher(
                views.CreditListView.as_view(),
                views.CreditListViewV2.as_view(
                    view_type=views.ViewType.simple_search_form,
                ),
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
        name='credits_advanced_search',
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
            search_v2_view_dispatcher(
                views.CreditListView.as_view(
                    view_type=views.ViewType.export_download,
                ),
                views.CreditListViewV2.as_view(
                    view_type=views.ViewType.export_download,
                ),
            ),
        ),
        name='credits_export',
    ),
    url(
        r'^credits/email-export/$',
        security_test(
            search_v2_view_dispatcher(
                views.CreditListView.as_view(
                    view_type=views.ViewType.export_email,
                ),
                views.CreditListViewV2.as_view(
                    view_type=views.ViewType.export_email,
                ),
            ),
        ),
        name='credits_email_export',
    ),
    url(
        r'^credits/(?P<credit_id>\d+)/$',
        security_test(views.CreditDetailView.as_view()),
        name='credit_detail',
    ),

    # senders
    url(
        r'^senders/$',
        security_test(
            search_v2_view_dispatcher(
                views.SenderListView.as_view(),
                views.SenderListViewV2.as_view(
                    view_type=views.ViewType.simple_search_form,
                ),
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
        name='senders_advanced_search',
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
            search_v2_view_dispatcher(
                views.SenderListView.as_view(
                    view_type=views.ViewType.export_download,
                ),
                views.SenderListViewV2.as_view(
                    view_type=views.ViewType.export_download,
                ),
            ),
        ),
        name='senders_export',
    ),
    url(
        r'^senders/email-export/$',
        security_test(
            search_v2_view_dispatcher(
                views.SenderListView.as_view(
                    view_type=views.ViewType.export_email,
                ),
                views.SenderListViewV2.as_view(
                    view_type=views.ViewType.export_email,
                ),
            ),
        ),
        name='senders_email_export',
    ),
    url(
        r'^senders/(?P<sender_id>\d+)/$',
        security_test(views.SenderDetailView.as_view()),
        name='sender_detail',
    ),
    url(
        r'^senders/(?P<sender_id>\d+)/export/$',
        security_test(
            views.SenderDetailView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='sender_detail_export',
    ),
    url(
        r'^senders/(?P<sender_id>\d+)/email-export/$',
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
            search_v2_view_dispatcher(
                views.PrisonerListView.as_view(),
                views.PrisonerListViewV2.as_view(
                    view_type=views.ViewType.simple_search_form,
                ),
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
        name='prisoners_advanced_search',
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
            search_v2_view_dispatcher(
                views.PrisonerListView.as_view(
                    view_type=views.ViewType.export_download,
                ),
                views.PrisonerListViewV2.as_view(
                    view_type=views.ViewType.export_download,
                ),
            ),
        ),
        name='prisoners_export'
    ),
    url(
        r'^prisoners/email-export/$',
        security_test(
            search_v2_view_dispatcher(
                views.PrisonerListView.as_view(
                    view_type=views.ViewType.export_email,
                ),
                views.PrisonerListViewV2.as_view(
                    view_type=views.ViewType.export_email,
                ),
            ),
        ),
        name='prisoners_email_export',
    ),
    url(
        r'^prisoners/(?P<prisoner_id>\d+)/$',
        security_test(views.PrisonerDetailView.as_view()),
        name='prisoner_detail',
    ),
    url(
        r'^prisoners/(?P<prisoner_id>\d+)/export/$',
        security_test(
            views.PrisonerDetailView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='prisoner_detail_export',
    ),
    url(
        r'^prisoners/(?P<prisoner_id>\d+)/email-export/$',
        security_test(
            views.PrisonerDetailView.as_view(
                view_type=views.ViewType.export_email,
            )
        ),
        name='prisoner_detail_email_export',
    ),
    url(
        r'^prisoners/(?P<prisoner_id>\d+)/disbursements/$',
        security_test(views.PrisonerDisbursementDetailView.as_view()),
        name='prisoner_disbursement_detail',
    ),
    url(
        r'^prisoners/(?P<prisoner_id>\d+)/disbursements/export/$',
        security_test(
            views.PrisonerDisbursementDetailView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='prisoner_disbursement_detail_export',
    ),
    url(
        r'^prisoners/(?P<prisoner_id>\d+)/disbursements/email-export/$',
        security_test(
            views.PrisonerDisbursementDetailView.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='prisoner_disbursement_detail_email_export',
    ),

    # async-loaded nomis info
    url(
        r'^prisoner_image/(?P<prisoner_number>[A-Za-z0-9]*)/$',
        security_test(views.prisoner_image_view),
        name='prisoner_image',
    ),
    url(
        r'^prisoner_nomis_info/(?P<prisoner_number>[A-Za-z0-9]*)/$',
        security_test(views.prisoner_nomis_info_view),
        name='prisoner_nomis_info',
    ),

    # disbursements
    url(
        r'^disbursements/$',
        security_test(
            search_v2_view_dispatcher(
                views.DisbursementListView.as_view(),
                views.DisbursementListViewV2.as_view(
                    view_type=views.ViewType.simple_search_form,
                ),
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
        name='disbursements_advanced_search',
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
            search_v2_view_dispatcher(
                views.DisbursementListView.as_view(
                    view_type=views.ViewType.export_download,
                ),
                views.DisbursementListViewV2.as_view(
                    view_type=views.ViewType.export_download,
                ),
            ),
        ),
        name='disbursements_export',
    ),
    url(
        r'^disbursements/email-export/$',
        security_test(
            search_v2_view_dispatcher(
                views.DisbursementListView.as_view(
                    view_type=views.ViewType.export_email,
                ),
                views.DisbursementListViewV2.as_view(
                    view_type=views.ViewType.export_email,
                ),
            ),
        ),
        name='disbursements_email_export',
    ),
    url(
        r'^disbursements/(?P<disbursement_id>\d+)/$',
        security_test(views.DisbursementDetailView.as_view()),
        name='disbursement_detail',
    ),

    # review credits
    url(
        r'^review-credits/$',
        security_test(views.ReviewCreditsView.as_view()),
        name='review_credits',
    ),

    # notifications
    url(
        r'^notifications/$',
        security_test(views.NotificationListView.as_view()),
        name='notification_list',
    ),
]
