import os

from django.core.urlresolvers import reverse
from mtp_common.test_utils.functional_tests import FunctionalTestCase


class PrisonerLocationAdminTestCase(FunctionalTestCase):
    """
    Base class for all prisoner-location-admin functional tests
    """
    accessibility_scope_selector = '#content'


class ErrorTests(PrisonerLocationAdminTestCase):
    """
    Tests for general errors
    """
    def test_404(self):
        self.driver.get(self.live_server_url + '/unknown-page/')
        self.assertInSource('Page not found')


class LoginTests(PrisonerLocationAdminTestCase):
    """
    Tests for Login page
    """

    def test_title(self):
        self.driver.get(self.live_server_url)
        heading = self.driver.find_element_by_tag_name('h1')
        self.assertEqual('NOMS admin', heading.text)
        self.assertEqual('48px', heading.value_of_css_property('font-size'))

    def test_bad_login(self):
        self.login('prisoner-location-admin', 'bad-password')
        self.assertInSource('There was a problem')

    def test_good_login(self):
        self.login('prisoner-location-admin', 'prisoner-location-admin')
        self.assertCurrentUrl(reverse('location_file_upload'))
        self.assertInSource('Upload location file')

    def test_logout(self):
        self.login('prisoner-location-admin', 'prisoner-location-admin')
        self.driver.find_element_by_link_text('Sign out').click()
        self.assertCurrentUrl(reverse('login'))


class UploadTests(PrisonerLocationAdminTestCase):
    """
    Tests for Upload functionality
    """

    def setUp(self):
        super().setUp()
        self.login('prisoner-location-admin', 'prisoner-location-admin')
        self.driver.execute_script('document.getElementById("id_location_file").style.left = 0')

    def test_checking_upload_page(self):
        self.assertInSource('Upload location file')
        self.assertInSource('upload the file on this page in CSV format')
        self.assertCssProperty('.upload-otherfilelink', 'display', 'none')

    def test_upload_valid_file(self):
        el = self.driver.find_element_by_xpath('//input[@type="file"]')
        el.send_keys(os.path.join(os.path.dirname(__file__), 'files', 'valid.csv'))
        self.assertInSource('Change file')
        el.submit()
        self.assertInSource('316 prisoner locations updated successfully')
        self.assertCssProperty('.upload-otherfilelink', 'display', 'block')

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
