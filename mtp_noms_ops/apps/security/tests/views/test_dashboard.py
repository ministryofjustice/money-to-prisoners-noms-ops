from django.core.urlresolvers import reverse
import responses

from security.tests.views.test_base import SecurityBaseTestCase, no_saved_searches


class SecurityDashboardViewsTestCase(SecurityBaseTestCase):
    @responses.activate
    def test_can_access_security_dashboard(self):
        response = self.login()
        self.assertContains(response, '<!-- security:dashboard -->')

    @responses.activate
    def test_cannot_access_prisoner_location_admin(self):
        self.login()
        no_saved_searches()
        response = self.client.get(reverse('location_file_upload'), follow=True)
        self.assertNotContains(response, '<!-- location_file_upload -->')
        self.assertContains(response, '<!-- security:dashboard -->')
