from urllib.parse import urljoin

from django.core.urlresolvers import reverse

from mtp_common.test_utils.functional_tests import FunctionalTestCase


class SecurityDashboardTestCase(FunctionalTestCase):
    """
    Base class for all NOMS security operations functional tests
    """
    accessibility_scope_selector = '#content'


class SecurityDashboardTests(SecurityDashboardTestCase):
    """
    Tests for the Security Dashboard
    """

    def test_login_redirects_to_security_dashboard(self):
        self.login('security-staff', 'security-staff')
        self.assertInSource('Search by sender')
        self.assertEqual(self.driver.title, 'NOMS admin')

    def test_superuser_can_see_prisoner_location_link(self):
        self.login('admin', 'adminadmin')
        prisoner_location_url = reverse('location_file_upload')
        security_url = reverse('security:dashboard')
        self.driver.get(urljoin(self.live_server_url, security_url))
        self.assertCurrentUrl(security_url)
        self.assertInSource(prisoner_location_url)
