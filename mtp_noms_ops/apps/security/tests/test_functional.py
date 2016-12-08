import logging
from urllib.parse import urljoin

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
        self.assertInSource('From one sender to many prisoners')
        self.assertEqual(self.driver.title, 'NOMS admin')

    def test_superuser_can_see_prisoner_location_link(self):
        self.login('admin', 'adminadmin')
        prisoner_location_url = reverse('location_file_upload')
        security_url = reverse('security:dashboard')
        self.driver.get(urljoin(self.live_server_url, security_url))
        self.assertCurrentUrl(security_url)
        self.assertInSource(prisoner_location_url)


class SecurityCreditSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('All credits')

    def test_search_by_other_results_show_sender(self):
        self.click_on_submit()
        self.assertInSource('<th>Sender</th>')


class SecuritySenderSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('From one sender to many prisoners')

    def test_headers_show_all_fields(self):
        self.click_on_submit()
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
        self.click_on_submit()
        self.assertInSource('Credits:')
        self.assertInSource('Senders:')
        self.assertInSource('Total: £')
        self.assertInSource('To:')
