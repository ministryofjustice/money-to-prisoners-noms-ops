from unittest import mock

from django.test import SimpleTestCase

from security import SEARCH_V2_FLAG
from security.urls import search_v2_view_redirect


class SearchV2ViewRedirectTestCase(SimpleTestCase):
    """
    Tests related to the search_v2_view_redirect function.
    """

    @mock.patch('security.urls.redirect')
    def test_legacy_search_view_redirects_to_v2_view_with_flag_on(self, mocked_redirect):
        """
        Test that the decorator redirects to the search v2 view passed in if the logged in
        user has the SEARCH_V2_FLAG on.
        """
        legacy_view_mock = mock.Mock()
        request = mock.Mock()
        request.user.user_data = {
            'flags': [SEARCH_V2_FLAG],
        }

        actual_view = search_v2_view_redirect(
            legacy_view_mock,
            search_v2_redirect_view_name='search_v2_redirect_view_name',
        )
        actual_view(request=request)

        mocked_redirect.assert_called_once_with('search_v2_redirect_view_name')

    @mock.patch('security.urls.redirect')
    def test_legacy_search_view_does_not_redirect_to_legacy_view_with_flag_off(self, mocked_redirect):
        """
        Test that the decorator does not redirect to the search v2 view passed in if the logged in
        user doesn't have the SEARCH_V2_FLAG on.
        """
        legacy_view_mock = mock.Mock()
        request = mock.Mock()
        request.user.user_data = {
            'flags': [],
        }

        actual_view = search_v2_view_redirect(
            legacy_view_mock,
            search_v2_redirect_view_name='search_v2_redirect_view_name',
        )
        actual_view(request=request)

        mocked_redirect.assert_not_called()

    @mock.patch('security.urls.redirect')
    def test_search_view_v2_redirects_to_legacy_view_with_flag_off(self, mocked_redirect):
        """
        Test that the decorator redirects to the legacy search view passed in if the logged in
        user doesn't have the SEARCH_V2_FLAG on.
        """
        view_mock = mock.Mock()
        request = mock.Mock()
        request.user.user_data = {
            'flags': [],
        }

        actual_view = search_v2_view_redirect(
            view_mock,
            legacy_search_redirect_view_name='legacy_search_redirect_view_name',
        )
        actual_view(request=request)

        mocked_redirect.assert_called_once_with('legacy_search_redirect_view_name')

    @mock.patch('security.urls.redirect')
    def test_search_view_v2_does_not_redirect_to_v2_view_with_flag_on(self, mocked_redirect):
        """
        Test that the decorator does not redirect to the legacy view passed in if the logged in
        user has the SEARCH_V2_FLAG on.
        """
        view_mock = mock.Mock()
        request = mock.Mock()
        request.user.user_data = {
            'flags': [SEARCH_V2_FLAG],
        }

        actual_view = search_v2_view_redirect(
            view_mock,
            legacy_search_redirect_view_name='legacy_search_redirect_view_name',
        )
        actual_view(request=request)

        mocked_redirect.assert_not_called()
