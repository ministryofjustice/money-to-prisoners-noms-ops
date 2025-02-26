from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import re_path

from mtp_noms_ops.utils import user_test
from security import required_permissions, views
from security.utils import (
    can_manage_security_checks,
    can_skip_confirming_prisons,
    is_hmpps_employee,
    has_provided_job_information,
)


def security_test(view, extra_tests=None):
    view = user_passes_test(
        has_provided_job_information,
        login_url='job_information',
    )(view)
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


app_name = 'security'
urlpatterns = [
    re_path(
        r'^$',
        security_test(views.DashboardView.as_view()),
        name='dashboard',
    ),
    re_path(
        r'^confirm-hmpps-employee/$',
        login_required(views.HMPPSEmployeeView.as_view()),
        name='hmpps_employee',
    ),
    re_path(r'^not-employee/$', views.NotHMPPSEmployeeView.as_view(), name='not_hmpps_employee'),
    re_path(r'^faq/$', login_required(views.FAQView.as_view()), name='faq'),
    re_path(
        r'^policy-change/$',
        login_required(views.PolicyChangeView.as_view()),
        name='policy_change'
    ),

    # credits
    re_path(
        r'^credits/$',
        security_test(
            views.CreditListView.as_view(
                view_type=views.ViewType.simple_search_form,
            ),
        ),
        name='credit_list',
    ),
    re_path(
        r'^credits/advanced-search/$',
        security_test(
            views.CreditListView.as_view(
                view_type=views.ViewType.advanced_search_form,
            ),
        ),
        name='credit_advanced_search',
    ),
    re_path(
        r'^credits/search-results/$',
        security_test(
            views.CreditListView.as_view(
                view_type=views.ViewType.search_results,
            ),
        ),
        name='credit_search_results',
    ),
    re_path(
        r'^credits/export/$',
        security_test(
            views.CreditListView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='credit_export',
    ),
    re_path(
        r'^credits/email-export/$',
        security_test(
            views.CreditListView.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='credit_email_export',
    ),
    re_path(
        r'^credits/(?P<credit_id>\d+)/$',
        security_test(views.CreditDetailView.as_view()),
        name='credit_detail',
    ),

    # senders
    re_path(
        r'^senders/$',
        security_test(
            views.SenderListView.as_view(
                view_type=views.ViewType.simple_search_form,
            ),
        ),
        name='sender_list',
    ),
    re_path(
        r'^senders/advanced-search/$',
        security_test(
            views.SenderListView.as_view(
                view_type=views.ViewType.advanced_search_form,
            ),
        ),
        name='sender_advanced_search',
    ),
    re_path(
        r'^senders/search-results/$',
        security_test(
            views.SenderListView.as_view(
                view_type=views.ViewType.search_results,
            ),
        ),
        name='sender_search_results',
    ),
    re_path(
        r'^senders/export/$',
        security_test(
            views.SenderListView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='sender_export',
    ),
    re_path(
        r'^senders/email-export/$',
        security_test(
            views.SenderListView.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='sender_email_export',
    ),
    re_path(
        r'^senders/(?P<sender_id>\d+)/$',
        security_test(views.SenderDetailView.as_view()),
        name='sender_detail',
    ),
    re_path(
        r'^senders/(?P<sender_id>\d+)/export/$',
        security_test(
            views.SenderDetailView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='sender_detail_export',
    ),
    re_path(
        r'^senders/(?P<sender_id>\d+)/email-export/$',
        security_test(
            views.SenderDetailView.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='sender_detail_email_export',
    ),

    # prisoners
    re_path(
        r'^prisoners/$',
        security_test(
            views.PrisonerListView.as_view(
                view_type=views.ViewType.simple_search_form,
            ),
        ),
        name='prisoner_list',
    ),
    re_path(
        r'^prisoners/advanced-search/$',
        security_test(
            views.PrisonerListView.as_view(
                view_type=views.ViewType.advanced_search_form,
            ),
        ),
        name='prisoner_advanced_search',
    ),
    re_path(
        r'^prisoners/search-results/$',
        security_test(
            views.PrisonerListView.as_view(
                view_type=views.ViewType.search_results,
            ),
        ),
        name='prisoner_search_results',
    ),
    re_path(
        r'^prisoners/search-results/disbursements/$',
        security_test(
            views.PrisonerDisbursementListView.as_view(
                view_type=views.ViewType.search_results,
            ),
        ),
        name='prisoner_disbursement_search_results',
    ),
    re_path(
        r'^prisoners/export/$',
        security_test(
            views.PrisonerListView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='prisoner_export'
    ),
    re_path(
        r'^prisoners/email-export/$',
        security_test(
            views.PrisonerListView.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='prisoner_email_export',
    ),
    re_path(
        r'^prisoners/(?P<prisoner_id>\d+)/$',
        security_test(views.PrisonerDetailView.as_view()),
        name='prisoner_detail',
    ),
    re_path(
        r'^prisoners/(?P<prisoner_id>\d+)/export/$',
        security_test(
            views.PrisonerDetailView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='prisoner_detail_export',
    ),
    re_path(
        r'^prisoners/(?P<prisoner_id>\d+)/email-export/$',
        security_test(
            views.PrisonerDetailView.as_view(
                view_type=views.ViewType.export_email,
            )
        ),
        name='prisoner_detail_email_export',
    ),
    re_path(
        r'^prisoners/(?P<prisoner_id>\d+)/disbursements/$',
        security_test(views.PrisonerDisbursementDetailView.as_view()),
        name='prisoner_disbursement_detail',
    ),
    re_path(
        r'^prisoners/(?P<prisoner_id>\d+)/disbursements/export/$',
        security_test(
            views.PrisonerDisbursementDetailView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='prisoner_disbursement_detail_export',
    ),
    re_path(
        r'^prisoners/(?P<prisoner_id>\d+)/disbursements/email-export/$',
        security_test(
            views.PrisonerDisbursementDetailView.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='prisoner_disbursement_detail_email_export',
    ),

    # async-loaded nomis info
    re_path(
        r'^prisoner-image/(?P<prisoner_number>[A-Za-z0-9]*)/$',
        security_test(views.prisoner_image_view),
        name='prisoner_image',
    ),
    re_path(
        r'^prisoner-info/(?P<prisoner_number>[A-Za-z0-9]*)/$',
        security_test(views.prisoner_nomis_info_view),
        name='prisoner_nomis_info',
    ),

    # disbursements
    re_path(
        r'^disbursements/$',
        security_test(
            views.DisbursementListView.as_view(
                view_type=views.ViewType.simple_search_form,
            ),
        ),
        name='disbursement_list',
    ),
    re_path(
        r'^disbursements/advanced-search/$',
        security_test(
            views.DisbursementListView.as_view(
                view_type=views.ViewType.advanced_search_form,
            ),
        ),
        name='disbursement_advanced_search',
    ),
    re_path(
        r'^disbursements/search-results/$',
        security_test(
            views.DisbursementListView.as_view(
                view_type=views.ViewType.search_results,
            ),
        ),
        name='disbursement_search_results',
    ),
    re_path(
        r'^disbursements/export/$',
        security_test(
            views.DisbursementListView.as_view(
                view_type=views.ViewType.export_download,
            ),
        ),
        name='disbursement_export',
    ),
    re_path(
        r'^disbursements/email-export/$',
        security_test(
            views.DisbursementListView.as_view(
                view_type=views.ViewType.export_email,
            ),
        ),
        name='disbursement_email_export',
    ),
    re_path(
        r'^disbursements/(?P<disbursement_id>\d+)/$',
        security_test(views.DisbursementDetailView.as_view()),
        name='disbursement_detail',
    ),

    # review credits
    re_path(
        r'^review-credits/$',
        security_test(views.ReviewCreditsView.as_view()),
        name='review_credits',
    ),

    # notifications
    re_path(
        r'^notifications/$',
        security_test(views.NotificationListView.as_view()),
        name='notification_list',
    ),

    # checks
    re_path(
        r'^checks/$',
        fiu_security_test(views.CheckListView.as_view()),
        name='check_list',
    ),
    re_path(
        r'^checks/my-list/$',
        fiu_security_test(views.MyCheckListView.as_view()),
        name='my_check_list',
    ),
    re_path(
        r'^checks/auto-accept-rules/$',
        fiu_security_test(views.AutoAcceptRuleListView.as_view()),
        name='auto_accept_rule_list',
    ),
    re_path(
        r'^checks/auto-accept-rules/(?P<auto_accept_rule_id>\d+)/$',
        fiu_security_test(views.AutoAcceptRuleDetailView.as_view()),
        name='auto_accept_rule_detail',
    ),
    re_path(
        r'^checks/(?P<check_id>\d+)/resolve/$',
        fiu_security_test(views.AcceptOrRejectCheckView.as_view()),
        name='resolve_check',
    ),
    re_path(
        r'^checks/(?P<check_id>\d+)/assignment/list/(?P<page>\d+)/$',
        fiu_security_test(views.CheckAssignView.as_view(redirect_to_list=True)),
        name='assign_check_then_list',
    ),
    re_path(
        r'^checks/(?P<check_id>\d+)/assignment/$',
        fiu_security_test(views.CheckAssignView.as_view(redirect_to_list=False)),
        name='assign_check',
    ),
    re_path(
        r'^checks/history/$',
        fiu_security_test(views.CheckHistoryListView.as_view()),
        name='check_history',
    ),
    re_path(
        r'^checks/monitored-email-addresses/$',
        fiu_security_test(views.MonitoredPartialEmailAddressListView.as_view()),
        name='monitored_email_addresses',
    ),
    re_path(
        r'^checks/monitored-email-addresses/add/$',
        fiu_security_test(views.MonitoredPartialEmailAddressAddView.as_view()),
        name='add_monitored_email_address',
    ),
    re_path(
        r'^checks/monitored-email-addresses/remove/$',
        fiu_security_test(views.MonitoredPartialEmailAddressDeleteView.as_view()),
        name='delete_monitored_email_address',
    ),
]
