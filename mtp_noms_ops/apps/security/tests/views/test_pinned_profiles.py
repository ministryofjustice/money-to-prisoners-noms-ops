import responses

from security.tests.utils import api_url
from security.tests.views.test_base import SecurityViewTestCase


class PinnedProfileTestCase(SecurityViewTestCase):

    @responses.activate
    def test_pinned_profiles_on_dashboard(self):
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 2,
                'results': [
                    {
                        'id': 1,
                        'description': 'Saved search 1',
                        'endpoint': '/prisoners/1/credits',
                        'last_result_count': 2,
                        'site_url': '/en-gb/security/prisoners/1/',
                        'filters': []
                    },
                    {
                        'id': 2,
                        'description': 'Saved search 2',
                        'endpoint': '/senders/1/credits',
                        'last_result_count': 3,
                        'site_url': '/en-gb/security/senders/1/',
                        'filters': []
                    }
                ]
            },
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/1/credits/'),
            json={
                'count': 5,
                'results': []
            },
        )
        responses.add(
            responses.GET,
            api_url('/senders/1/credits/'),
            json={
                'count': 10,
                'results': []
            },
        )
        response = self.login_test_searches()

        self.assertContains(response, 'Saved search 1')
        self.assertContains(response, 'Saved search 2')
        self.assertContains(response, '3 new credits')
        self.assertContains(response, '7 new credits')

    @responses.activate
    def test_removes_invalid_saved_searches(self):
        responses.add(
            responses.GET,
            api_url('/searches/'),
            json={
                'count': 2,
                'results': [
                    {
                        'id': 1,
                        'description': 'Saved search 1',
                        'endpoint': '/prisoners/1/credits',
                        'last_result_count': 2,
                        'site_url': '/en-gb/security/prisoners/1/',
                        'filters': []
                    },
                    {
                        'id': 2,
                        'description': 'Saved search 2',
                        'endpoint': '/senders/1/credits',
                        'last_result_count': 3,
                        'site_url': '/en-gb/security/senders/1/',
                        'filters': []
                    }
                ]
            },
        )
        responses.add(
            responses.GET,
            api_url('/prisoners/1/credits/'),
            json={
                'count': 5,
                'results': []
            },
        )
        responses.add(
            responses.GET,
            api_url('/senders/1/credits/'),
            status=404,
        )
        responses.add(
            responses.DELETE,
            api_url('/searches/2/'),
            status=201,
        )
        response = self.login_test_searches()

        self.assertContains(response, 'Saved search 1')
        self.assertNotContains(response, 'Saved search 2')
        self.assertContains(response, '3 new credits')
