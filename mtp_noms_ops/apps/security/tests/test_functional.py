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

    def setUp(self):
        super().setUp()
        self.login('security-staff', 'security-staff')

    def test_login_redirects_to_security_dashboard(self):
        self.assertInSource('Search by sender')
        self.assertEqual(self.driver.title, 'NOMS admin')
