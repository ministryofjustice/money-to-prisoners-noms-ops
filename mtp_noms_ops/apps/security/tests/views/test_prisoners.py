import base64
import json

from django.core.urlresolvers import reverse
from mtp_common.test_utils import silence_logger
import responses

from security.tests.utils import api_url, nomis_url, TEST_IMAGE_DATA
from security.tests.views.test_base import (
    ExportSecurityViewTestCaseMixin,
    no_saved_searches,
    override_nomis_settings,
    sample_prison_list,
    SecurityViewTestCase,
    SimpleSearchV2SecurityTestCaseMixin,
)


class PrisonerViewsTestCase(SecurityViewTestCase):
    """
    TODO: delete after search V2 goes live.
    """
    view_name = 'security:prisoner_list'
    detail_view_name = 'security:prisoner_detail'
    api_list_path = '/prisoners/'

    @responses.activate
    def test_displays_results(self):
        self.login()
        no_saved_searches()
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url(self.api_list_path),
            json={
                'count': 1,
                'results': [self.prisoner_profile],
            }
        )
        response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'JAMES HALLS')
        response_content = response.content.decode(response.charset)
        self.assertIn('A1409AE', response_content)
        self.assertIn('310.00', response_content)

    @responses.activate
    @override_nomis_settings
    def test_displays_detail(self):
        self.login()
        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/'.format(id=9)),
            json=self.prisoner_profile
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/credits/'.format(id=9)),
            json={
                'count': 4,
                'results': [self.credit_object, self.credit_object, self.credit_object, self.credit_object],
            }
        )

        response = self.client.get(reverse(
            self.detail_view_name, kwargs={'prisoner_id': 9}))
        self.assertContains(response, 'JAMES HALLS')
        response_content = response.content.decode(response.charset)
        self.assertIn('Jim Halls', response_content)
        self.assertNotIn('James Halls', response_content)
        self.assertIn('MAISIE', response_content)
        self.assertIn('£102.50', response_content)

    @responses.activate
    def test_detail_not_found(self):
        self.login()
        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/'.format(id=9)),
            status=404
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/credits/'.format(id=9)),
            status=404
        )
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'prisoner_id': 9}))
        self.assertEqual(response.status_code, 404)

    @responses.activate
    def test_connection_errors(self):
        self.login()
        no_saved_searches()
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/'.format(id=9)),
            status=500
        )
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'non-field-error')

        no_saved_searches()
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/'.format(id=9)),
            status=500
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/{id}/credits/'.format(id=9)),
            status=500
        )
        with silence_logger('django.request'):
            response = self.client.get(reverse(self.detail_view_name, kwargs={'prisoner_id': 9}))
        self.assertContains(response, 'non-field-error')


class PrisonerViewsV2TestCase(
    SimpleSearchV2SecurityTestCaseMixin,
    ExportSecurityViewTestCaseMixin,
    SecurityViewTestCase,
):
    """
    Test case related to prisoner search V2 and detail views.
    """
    view_name = 'security:prisoner_list'
    search_results_view_name = 'security:prisoner_search_results'
    detail_view_name = 'security:prisoner_detail'
    search_ordering = '-sender_count'
    api_list_path = '/prisoners/'

    export_view_name = 'security:prisoners_export'
    export_email_view_name = 'security:prisoners_email_export'
    export_expected_xls_headers = [
        'Prisoner number',
        'Prisoner name',
        'Date of birth',
        'Credits received',
        'Total amount received',
        'Payment sources',
        'Current prison',
        'Prisons where received credits',
        'Names given by senders',
        'Disbursements sent',
        'Total amount sent',
        'Recipients',
    ]
    export_expected_xls_rows = [
        [
            'A1409AE',
            'JAMES HALLS',
            '1986-12-09',
            3,
            '£310.00',
            2,
            'Prison',
            'Prison',
            'Jim Halls, JAMES HALLS',
            2,
            '£290.00',
            1,
        ],
    ]

    def get_api_object_list_response_data(self):
        return [self.prisoner_profile]

    def _test_simple_search_search_results_content(self, response):
        response_content = response.content.decode(response.charset)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('A1409AE', response_content)
        self.assertIn('310.00', response_content)

    @override_nomis_settings
    def test_detail_view(self):
        prisoner_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/'),
                json=self.prisoner_profile,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/credits/'),
                json={
                    'count': 4,
                    'results': [self.credit_object] * 4,
                },
            )

            response = self.client.get(
                reverse(
                    self.detail_view_name,
                    kwargs={'prisoner_id': prisoner_id},
                ),
            )
        response_content = response.content.decode(response.charset)
        self.assertIn('JAMES HALLS', response_content)
        self.assertIn('Jim Halls', response_content)
        self.assertNotIn('James Halls', response_content)
        self.assertIn('MAISIE', response_content)
        self.assertIn('£102.50', response_content)

    def test_detail_not_found(self):
        prisoner_id = 999
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/'),
                status=404,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/credits/'),
                status=404,
            )
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'prisoner_id': prisoner_id},
                    ),
                )
        self.assertEqual(response.status_code, 404)

    def test_connection_errors(self):
        prisoner_id = 9
        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            sample_prison_list(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(self.api_list_path),
                status=500,
            )
            with silence_logger('django.request'):
                response = self.client.get(reverse(self.view_name))
        self.assertContains(response, 'non-field-error')

        with responses.RequestsMock() as rsps:
            self.login(rsps=rsps)
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/'),
                status=500,
            )
            rsps.add(
                rsps.GET,
                api_url(f'/prisoners/{prisoner_id}/credits/'),
                status=500,
            )
            with silence_logger('django.request'):
                response = self.client.get(
                    reverse(
                        self.detail_view_name,
                        kwargs={'prisoner_id': prisoner_id},
                    ),
                )
        self.assertContains(response, 'non-field-error')


class PrisonerDetailViewTestCase(SecurityViewTestCase):
    def _add_prisoner_data_responses(self):
        responses.add(
            responses.GET,
            api_url('/prisoners/1/'),
            json=self.prisoner_profile,
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/1/credits/'),
            json={
                'count': 4,
                'results': [
                    self.credit_object, self.credit_object,
                    self.credit_object, self.credit_object
                ],
            },
        )

    @responses.activate
    @override_nomis_settings
    def test_display_nomis_photo(self):
        responses.add(
            responses.GET,
            nomis_url('/offenders/{prisoner_number}/image'.format(
                prisoner_number=self.prisoner_profile['prisoner_number'])),
            json={
                'image': TEST_IMAGE_DATA
            },
        )
        self.login(follow=False)
        response = self.client.get(
            reverse(
                'security:prisoner_image',
                kwargs={'prisoner_number': self.prisoner_profile['prisoner_number']}
            )
        )
        self.assertContains(response, base64.b64decode(TEST_IMAGE_DATA))

    @responses.activate
    @override_nomis_settings
    def test_missing_nomis_photo(self):
        responses.add(
            responses.GET,
            nomis_url('/offenders/{prisoner_number}/image'.format(
                prisoner_number=self.prisoner_profile['prisoner_number'])),
            json={
                'image': None
            },
        )
        self.login(follow=False)
        response = self.client.get(
            reverse(
                'security:prisoner_image',
                kwargs={'prisoner_number': self.prisoner_profile['prisoner_number']}
            ),
            follow=False
        )
        self.assertRedirects(response, '/static/images/placeholder-image.png', fetch_redirect_response=False)

    @responses.activate
    @override_nomis_settings
    def test_display_pinned_profile(self):
        self._add_prisoner_data_responses()
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 1,
                'results': [
                    {
                        'id': 1,
                        'description': 'Saved search 1',
                        'endpoint': '/prisoners/1/credits/',
                        'last_result_count': 2,
                        'site_url': '/en-gb/security/prisoners/1/?ordering=-received_at',
                        'filters': []
                    },
                ]
            },
        )
        responses.add(
            responses.PATCH,
            api_url('/searches/1/'),
            status=204,
        )
        self.login(follow=False)
        response = self.client.get(
            reverse('security:prisoner_detail', kwargs={'prisoner_id': 1})
        )
        self.assertContains(response, 'Stop monitoring this prisoner')
        for call in responses.calls:
            if call.request.path_url == '/searches/1/':
                self.assertEqual(call.request.body, b'{"last_result_count": 4}')

    @responses.activate
    @override_nomis_settings
    def test_pin_profile(self):
        self._add_prisoner_data_responses()
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 0,
                'results': []
            },
        )
        responses.add(
            responses.POST,
            api_url('/searches/'),
            status=201,
        )
        responses.add(
            responses.POST,
            api_url('/prisoners/1/monitor'),
            status=204,
        )

        self.login(follow=False)
        self.client.get(
            reverse('security:prisoner_detail', kwargs={'prisoner_id': 1}) +
            '?pin=1'
        )

        for call in responses.calls:
            if call.request.path_url == '/searches/':
                self.assertEqual(
                    json.loads(call.request.body.decode()),
                    {
                        'description': 'A1409AE JAMES HALLS',
                        'endpoint': '/prisoners/1/credits/',
                        'last_result_count': 4,
                        'site_url': '/en-gb/security/prisoners/1/',
                        'filters': [{'field': 'ordering', 'value': '-received_at'}],
                    },
                )
