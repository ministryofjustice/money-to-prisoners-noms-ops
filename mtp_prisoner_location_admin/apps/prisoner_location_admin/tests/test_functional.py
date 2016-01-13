import os
import unittest

from django.test import LiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.keys import Keys


@unittest.skipUnless('RUN_FUNCTIONAL_TESTS' in os.environ, 'functional tests are disabled')
class FunctionalTestCase(LiveServerTestCase):
    """
    Base class to define common methods to test subclasses below
    """

    @classmethod
    def _databases_names(cls, include_mirrors=True):
        # this app has no databases
        return []

    def setUp(self):
        path = './node_modules/phantomjs/lib/phantom/bin/phantomjs'
        self.driver = webdriver.PhantomJS(executable_path=path)
        self.driver.set_window_size(1000, 1000)

    def tearDown(self):
        self.driver.quit()

    def login(self, username, password):
        self.driver.get(self.live_server_url)
        login_field = self.driver.find_element_by_id('id_username')
        login_field.send_keys(username)
        password_field = self.driver.find_element_by_id('id_password')
        password_field.send_keys(password + Keys.RETURN)

    def login_and_go_to(self, link_text):
        self.login('prisoner-location-admin', 'prisoner-location-admin')
        self.driver.find_element_by_partial_link_text(link_text).click()


class LoginTests(FunctionalTestCase):
    """
    Tests for Login page
    """

    def test_title(self):
        self.driver.get(self.live_server_url)
        heading = self.driver.find_element_by_tag_name('h1')
        self.assertEquals('Upload prisoner locations', heading.text)
        self.assertEquals('48px', heading.value_of_css_property('font-size'))

    def test_bad_login(self):
        self.login('prisoner-location-admin', 'bad-password')
        self.assertIn('There was a problem submitting the form',
                      self.driver.page_source)

    def test_good_login(self):
        self.login('prisoner-location-admin', 'prisoner-location-admin')
        self.assertEquals(self.driver.current_url, self.live_server_url + '/')
        self.assertIn('Upload location file', self.driver.page_source)

    def test_logout(self):
        self.login('prisoner-location-admin', 'prisoner-location-admin')
        self.driver.find_element_by_link_text('Sign out').click()
        self.assertEqual(self.driver.current_url.split('?')[0], self.live_server_url + '/login/')


class UploadTests(FunctionalTestCase):
    """
    Tests for Upload functionality
    """

    def setUp(self):
        super().setUp()
        self.login('prisoner-location-admin', 'prisoner-location-admin')

    def test_checking_upload_page(self):
        self.assertIn('Upload location file', self.driver.page_source)

    def test_upload_valid_file(self):
        el = self.driver.find_element_by_xpath('//input[@type="file"]')
        el.send_keys(os.path.join(os.path.dirname(__file__), 'files', 'valid.csv'))
        el.submit()
        self.assertIn('File uploaded successfully!', self.driver.page_source)

    def test_upload_invalid_file(self):
        el = self.driver.find_element_by_xpath('//input[@type="file"]')
        el.send_keys(os.path.join(os.path.dirname(__file__), 'files', 'invalid.csv'))
        el.submit()
        self.assertIn('Row has 5 columns, should have 4', self.driver.page_source)

    def test_submit_file_upload_without_selecting_file(self):
        el = self.driver.find_element_by_xpath('//input[@type="file"]')
        el.submit()
        self.assertIn('This field is required', self.driver.page_source)
