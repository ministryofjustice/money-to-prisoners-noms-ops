import logging

from django.core.urlresolvers import reverse
from mtp_common.test_utils.functional_tests import FunctionalTestCase
from mtp_common.test_utils import silence_logger
from selenium.webdriver.common.keys import Keys


class SecurityDashboardTestCase(FunctionalTestCase):
    """
    Base class for all NOMS security operations functional tests
    """
    auto_load_test_data = True
    accessibility_scope_selector = '#content'

    def load_test_data(self):
        with silence_logger(name='mtp', level=logging.WARNING):
            super().load_test_data()
        # only need it the first time as data is not modified by these tests:
        SecurityDashboardTestCase.auto_load_test_data = False

    def login(self, *args, **kwargs):
        kwargs['url'] = self.live_server_url + '/en-gb/'
        super().login(*args, **kwargs)

    def click_on_submit(self):
        self.driver.find_element_by_xpath('//button[@type="submit"]').click()

    def click_on_tab(self, field):
        tab_element = self.driver.find_element_by_css_selector('#mtp-tab-%s' % field)
        tab_element.click()

    def submit_tabpanel(self, field):
        selector = '#mtp-tabpanel-%s button[type="submit"]' % field
        update_list_button = self.driver.find_element_by_css_selector(selector)
        update_list_button.click()


class SecurityDashboardTests(SecurityDashboardTestCase):
    """
    Tests for the Security Dashboard
    """

    def test_login_redirects_to_security_dashboard(self):
        self.login('security-staff', 'security-staff')
        self.assertInSource('Credits')
        self.assertInSource('Senders')
        self.assertInSource('Prisoners')
        self.assertEqual(self.driver.title, 'Security check')
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

        self.click_on_tab('sender')
        self.type_in('id_sender_name', 'aaabbbccc111222333')  # not a likely sender name
        self.submit_tabpanel('sender')
        self.assertInSource('No matching credits found')

        self.click_on_tab('prisoner')
        self.type_in('id_prisoner_name', 'James')  # combined search
        self.submit_tabpanel('prisoner')
        self.assertInSource('No matching credits found')

        self.click_on_tab('sender')
        self.type_in('id_sender_name', Keys.BACKSPACE * len('aaabbbccc111222333'))
        self.submit_tabpanel('sender')
        self.assertInSource('JAMES HALLS')

    def test_ordering(self):
        self.click_on_tab('amount')
        amount_pattern = self.get_element('id_amount_pattern')
        amount_pattern.find_element_by_xpath('//option[text()="Not a multiple of £5"]').click()
        self.submit_tabpanel('amount')
        search_description = self.get_element('.mtp-search-description__text')
        self.assertIn('Showing credits sent that are not a multiple of £5, ordered by received date',
                      search_description.text)

        self.get_element('.mtp-results-list th:nth-child(3) a').click()
        search_description = self.get_element('.mtp-search-description__text')
        self.assertIn('Showing credits sent that are not a multiple of £5, ordered by amount sent (low to high)',
                      search_description.text)


class SecuritySenderSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('Senders')

    def test_perform_searches(self):
        self.assertInSource('Sender and type')  # a results list header

        self.click_on_tab('sender')
        self.type_in('id_sender_name', 'aaabbbccc111222333')  # not a likely sender name
        self.submit_tabpanel('sender')
        self.assertInSource('No matching senders found')


class SecurityPrisonerSearchTests(SecurityDashboardTestCase):
    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')
        self.click_on_text('Prisoners')

    def test_perform_searches(self):
        self.assertInSource('Received')  # a results list header

        self.click_on_tab('prisoner')
        self.type_in('id_prisoner_name', 'James')
        self.submit_tabpanel('prisoner')
        self.assertInSource('JAMES HALLS')

        self.click_on_tab('prisoner')
        self.type_in('id_prisoner_name', 'aaabbbccc111222333')  # not a likely prisoner name
        self.submit_tabpanel('prisoner')
        self.assertInSource('No matching prisoners found')
