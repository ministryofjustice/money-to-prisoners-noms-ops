import logging
import os

from django.core.urlresolvers import reverse
from mtp_common.test_utils import silence_logger
from mtp_common.test_utils.functional_tests import FunctionalTestCase


class PrisonerLocationAdminTestCase(FunctionalTestCase):
    """
    Base class for all prisoner-location-admin functional tests
    """
    accessibility_scope_selector = '#content'

    def load_test_data(self):
        with silence_logger(name='mtp', level=logging.WARNING):
            super().load_test_data()

    def login(self, *args, **kwargs):
        kwargs['url'] = self.live_server_url + '/en-gb/'
        super().login(*args, **kwargs)


class ErrorTests(PrisonerLocationAdminTestCase):
    """
    Tests for general errors
    """

    @silence_logger(name='django.request', level=logging.ERROR)
    def test_404(self):
        self.driver.get(self.live_server_url + '/unknown-page/')
        self.assertInSource('Page not found')


class LoginTests(PrisonerLocationAdminTestCase):
    """
    Tests for Login page
    """

    def test_title(self):
        self.driver.get(self.live_server_url + '/en-gb/')
        heading = self.driver.find_element_by_tag_name('h1')
        self.assertEqual('Prisoner money intelligence\nSign in', heading.text)

    def test_bad_login(self):
        self.login('prisoner-location-admin', 'bad-password')
        self.assertInSource('There was a problem')

    def test_good_login(self):
        self.login('prisoner-location-admin', 'prisoner-location-admin')
        self.assertCurrentUrl(reverse('location_file_upload'))
        self.assertInSource('Upload prisoner location file')
        self.assertNotInSource('Prisoner money intelligence')

    def test_logout(self):
        self.login('prisoner-location-admin', 'prisoner-location-admin')
        self.driver.find_element_by_link_text('Sign out').click()
        self.assertCurrentUrl(reverse('login'))

    def test_superuser_can_see_security_link(self):
        self.login('admin', 'adminadmin')
        dashboard_url = reverse('dashboard')
        prisoner_location_url = reverse('location_file_upload')
        self.assertCurrentUrl(dashboard_url)
        self.assertInSource('Welcome')
        self.assertInSource(prisoner_location_url)


class UploadTests(PrisonerLocationAdminTestCase):
    """
    Tests for Upload functionality
    """
    auto_load_test_data = True

    def setUp(self):
        super().setUp()
        self.login('prisoner-location-admin', 'prisoner-location-admin')
        self.click_on_text_substring('Upload prisoner location file')
        self.driver.execute_script('document.getElementById("id_location_file").style.left = 0')

    def test_checking_upload_page(self):
        self.assertInSource('Upload prisoner location file')
        self.assertInSource('upload the file on this page in CSV format')
        self.assertCssProperty('.upload-otherfilelink', 'display', 'none')

    @silence_logger(name='mtp', level=logging.WARNING)
    def test_upload_valid_file(self):
        el = self.driver.find_element_by_xpath('//input[@type="file"]')
        el.send_keys(os.path.join(os.path.dirname(__file__), 'files', 'valid.csv'))
        self.assertInSource('Change file')
        el.submit()
        if os.environ.get('DJANGO_TEST_REMOTE_INTEGRATION_URL', None):
            self.assertInSource('316 prisoner locations scheduled for upload')
        else:
            self.assertInSource('316 prisoner locations updated successfully')

    def test_upload_invalid_file(self):
        el = self.driver.find_element_by_xpath('//input[@type="file"]')
        el.send_keys(os.path.join(os.path.dirname(__file__), 'files', 'invalid.csv'))
        el.submit()
        self.assertInSource('The file has the wrong number of columns')

    def test_upload_empty_file(self):
        el = self.driver.find_element_by_xpath('//input[@type="file"]')
        el.send_keys(os.path.join(os.path.dirname(__file__), 'files', 'empty.csv'))
        el.submit()
        self.assertInSource('The file doesn’t contain valid rows')

    def test_submit_file_upload_without_selecting_file(self):
        el = self.driver.find_element_by_xpath('//input[@type="file"]')
        el.submit()
        self.assertInSource('Please choose a file')
