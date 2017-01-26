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

    def click_on_nth_form_tab(self, n):
        tab_element = self.driver.find_element_by_css_selector('#tabs li:nth-child(%d) a' % n)
        tab_element.click()


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

    def test_perform_searches(self):
        self.assertInSource('Sender and type')  # a results list header
        self.click_on_nth_form_tab(4)
        self.type_in('id_sender_name', 'aaabbbccc111222333')  # not a likely sender name
        self.click_on_submit()
        self.assertInSource('No matching credits found')


class SecuritySenderSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('Senders')

    def test_perform_searches(self):
        self.assertInSource('Sender and type')  # a results list header
        self.click_on_nth_form_tab(1)
        self.type_in('id_sender_name', 'aaabbbccc111222333')  # not a likely sender name
        self.click_on_submit()
        self.assertInSource('No matching senders found')


class SecurityPrisonerSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('Prisoners')

    def test_perform_searches(self):
        self.assertInSource('Received')  # a results list header
        self.type_in('id_prisoner_name', 'James')
        self.click_on_submit()
        self.assertInSource('JAMES HALLS')
        self.type_in('id_prisoner_name', 'aaabbbccc111222333')  # not a likely prisoner name
        self.click_on_submit()
        self.assertInSource('No matching prisoners found')
