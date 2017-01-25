import logging

from django.core.urlresolvers import reverse
from mtp_common.test_utils.functional_tests import FunctionalTestCase
from mtp_common.test_utils import silence_logger


class SecurityDashboardTestCase(FunctionalTestCase):
    """
    Base class for all NOMS security operations functional tests
    """
    auto_load_test_data = True
    accessibility_scope_selector = '#content'

    def load_test_data(self):
        with silence_logger(name='mtp', level=logging.WARNING):
            super().load_test_data()

    def login(self, *args, **kwargs):
        kwargs['url'] = self.live_server_url + '/en-gb/'
        super().login(*args, **kwargs)

    def click_on_submit(self):
        self.driver.find_element_by_xpath('//button[@type="submit"]').click()


class SecurityDashboardTests(SecurityDashboardTestCase):
    """
    Tests for the Security Dashboard
    """

    def test_login_redirects_to_security_dashboard(self):
        self.login('security-staff', 'security-staff')
        self.assertInSource('Credits')
        self.assertInSource('Senders')
        self.assertInSource('Prisoners')
        self.assertEqual(self.driver.title, 'NOMS admin')
        dashboard_url = reverse('dashboard')
        prisoner_location_url = reverse('location_file_upload')
        self.assertCurrentUrl(dashboard_url)
        self.assertNotInSource(prisoner_location_url)

    def test_superuser_can_see_prisoner_location_link(self):
        self.login('admin', 'adminadmin')
        dashboard_url = reverse('dashboard')
        prisoner_location_url = reverse('location_file_upload')
        self.assertCurrentUrl(dashboard_url)
        self.assertInSource(prisoner_location_url)


class SecurityCreditSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('Credits')

    def test_search_results_show_sender(self):
        self.click_on_submit()
        self.assertInSource('<th>Sender and type</th>')


class SecuritySenderSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('Senders')

    def test_headers_show_all_fields(self):
        self.click_on_submit()
        self.assertInSource('<th>Sender and type</th>')
        self.assertInSource('<th>Sent</th>')
        self.assertInSource('<th>Prisoners</th>')
        self.assertInSource('<th>Prisons</th>')
        self.assertInSource('<th class="number">Amount</th>')


class SecurityPrisonerSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('Prisoners')

    def test_headers_show_all_fields(self):
        self.click_on_submit()
        self.assertInSource('<th>Prisoner</th>')
        self.assertInSource('<th>Prisoner</th>')
        self.assertInSource('<th>Prison</th>')
        self.assertInSource('<th>Received</th>')
        self.assertInSource('<th>Senders</th>')
        self.assertInSource('<th class="number">Amount</th>')
