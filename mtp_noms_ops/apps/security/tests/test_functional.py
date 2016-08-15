from urllib.parse import urljoin

from django.core.urlresolvers import reverse

from mtp_common.test_utils.functional_tests import FunctionalTestCase


class SecurityDashboardTestCase(FunctionalTestCase):
    """
    Base class for all NOMS security operations functional tests
    """
    auto_load_test_data = True
    accessibility_scope_selector = '#content'


class SecurityDashboardTests(SecurityDashboardTestCase):
    """
    Tests for the Security Dashboard
    """

    def test_login_redirects_to_security_dashboard(self):
        self.login('security-staff', 'security-staff')
        self.assertInSource('From one sender to many prisoners')
        self.assertEqual(self.driver.title, 'NOMS admin')

    def test_superuser_can_see_prisoner_location_link(self):
        self.login('admin', 'adminadmin')
        prisoner_location_url = reverse('location_file_upload')
        security_url = reverse('security:dashboard')
        self.driver.get(urljoin(self.live_server_url, security_url))
        self.assertCurrentUrl(security_url)
        self.assertInSource(prisoner_location_url)


class SecurityOtherSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('All transactions')

    def test_search_by_other_results_show_sender(self):
        self.click_on_text('Search')
        self.assertInSource('<th>Sender</th>')


class SecuritySenderSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('From one sender to many prisoners')

    def test_headers_show_all_fields(self):
        self.click_on_text('Search')
        self.assertInSource('Credits:')
        self.assertInSource('Prisoners:')
        self.assertInSource('Total: £')
        self.assertInSource('From:')


class SecurityPrisonerSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('To one prisoner from many senders')

    def test_headers_show_all_fields(self):
        self.click_on_text('Search')
        self.assertInSource('Credits:')
        self.assertInSource('Senders:')
        self.assertInSource('Total: £')
        self.assertInSource('To:')
