from unittest import mock

from django.test import SimpleTestCase

from security import SEARCH_V2_FLAG
from security.urls import search_v2_view_dispatcher


class SearchV2ViewDispatcherTestCase(SimpleTestCase):
    """
    Tests related to the search_v2_view_dispatcher function.
    """

    def test_with_flag(self):
        """
        Test that if the logged in user has the flag `SEARCH_V2_FLAG` set,
        he/she is redirected to the search V2.
        """
        legacy_view_mock = mock.Mock()
        search_v2_view_mock = mock.Mock()
        request = mock.Mock()
        request.user.user_data = {
            'flags': [SEARCH_V2_FLAG],
        }

        view = search_v2_view_dispatcher(legacy_view_mock, search_v2_view_mock)
        view(request=request)

        legacy_view_mock.assert_not_called()
        search_v2_view_mock.assert_called()

    def test_without_flag(self):
        """
        Test that if the logged in user doesn't have the flag `SEARCH_V2_FLAG` set,
        he/she is redirected to the previous legacy view.
        """
        legacy_view_mock = mock.Mock()
        search_v2_view_mock = mock.Mock()
        request = mock.Mock()
        request.user.user_data = {
            'flags': [],
        }

        view = search_v2_view_dispatcher(legacy_view_mock, search_v2_view_mock)
        view(request=request)

        legacy_view_mock.assert_called()
        search_v2_view_mock.assert_not_called()
