import datetime

from django import forms
from django.utils import timezone
from django.utils.functional import cached_property
from form_error_reporting import GARequestErrorReportingMixin
from mtp_common.api import retrieve_all_pages_for_path
from mtp_common.auth.api_client import get_api_session


class ReviewCreditsForm(GARequestErrorReportingMixin, forms.Form):
    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

        for credit in self.credits:
            self.fields['comment_%s' % credit['id']] = forms.CharField(required=False)

    @cached_property
    def session(self):
        return get_api_session(self.request)

    @cached_property
    def credits(self):
        prisons = [
            prison['nomis_id']
            for prison in self.request.user.user_data.get('prisons', [])
            if prison['pre_approval_required']
        ]
        return retrieve_all_pages_for_path(
            self.session, '/credits/', valid=True, reviewed=False, prison=prisons, resolution='pending',
            received_at__lt=datetime.datetime.combine(timezone.now().date(),
                                                      datetime.time(0, 0, 0, tzinfo=timezone.utc))
        )

    def review(self):
        reviewed = set()
        comments = []
        for credit in self.credits:
            reviewed.add(credit['id'])
            comment = self.cleaned_data['comment_%s' % credit['id']]

            if comment:
                comments.append({
                    'credit': credit['id'],
                    'comment': comment
                })
        if comments:
            self.session.post('/credits/comments/', json=comments)
        self.session.post('/credits/actions/review/', json={
            'credit_ids': list(reviewed)
        })

        return len(reviewed)
