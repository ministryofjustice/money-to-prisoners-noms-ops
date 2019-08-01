from django.core.urlresolvers import reverse
import responses

from security import (
    confirmed_prisons_flag,
    hmpps_employee_flag,
    SEARCH_V2_FLAG,
)
from security.tests.utils import api_url
from security.tests.views.test_base import (
    no_saved_searches,
    sample_prison_list,
    sample_prisons,
    SecurityBaseTestCase,
)


class PrisonSwitcherTestCase(SecurityBaseTestCase):
    """
    Tests related to the prison switcher area on the top of some pages.
    The prison switcher area shows the prisons that the user selected in the settings
    page with a link to change this.
    """

    def _mock_api_responses(self):
        no_saved_searches()
        sample_prison_list()
        responses.add(
            responses.GET,
            api_url('/senders/'),
            json={},
        )

    def get_user_data(
        self,
        *args,
        flags=(
            hmpps_employee_flag,
            confirmed_prisons_flag,
            SEARCH_V2_FLAG,
        ),
        **kwargs,
    ):
        """
        Sets the SEARCH_V2_FLAG feature flag by default.
        """

        return super().get_user_data(*args, flags=flags, **kwargs)

    @responses.activate
    def test_cannot_see_switcher_without_flag(self):
        """
        Test that the prison-switcher is not visible if the SEARCH_V2_FLAG flag for the user is not set.
        """
        self._mock_api_responses()
        prisons = [
            {
                **sample_prisons[0],
                'name': f'Prison {index}',
            } for index in range(1, 11)
        ]
        self.login(
            user_data=self.get_user_data(
                prisons=prisons,
                flags=(
                    hmpps_employee_flag,
                    confirmed_prisons_flag,
                ),
            ),
        )
        response = self.client.get(reverse('security:sender_list'))
        self.assertNotContains(
            response,
            'Prison 1, Prison 2, Prison 3, Prison 4',
        )
        self.assertNotContains(
            response,
            ' and 6 more',
        )

    @responses.activate
    def test_with_many_prisons(self):
        """
        Test that if the user has more than 4 prisons in settings, only the first ones are
        shown in the prison switcher area to avoid long text.
        """
        self._mock_api_responses()
        prisons = [
            {
                **sample_prisons[0],
                'name': f'Prison {index}',
            } for index in range(1, 11)
        ]
        self.login(
            user_data=self.get_user_data(prisons=prisons),
        )
        response = self.client.get(reverse('security:sender_list'))
        self.assertContains(
            response,
            'Prison 1, Prison 2, Prison 3, Prison 4',
        )
        self.assertContains(
            response,
            ' and 6 more',
        )

    @responses.activate
    def test_with_fewer_prisons(self):
        """
        Test that if the user has less than 4 prisons in settings,
        they are all shown in the prison switcher area.
        """
        self._mock_api_responses()
        prisons = [
            {
                **sample_prisons[0],
                'name': f'Prison {index}',
            } for index in range(1, 3)
        ]
        self.login(
            user_data=self.get_user_data(prisons=prisons),
        )
        response = self.client.get(reverse('security:sender_list'))
        self.assertContains(
            response,
            'Prison 1, Prison 2',
        )

        self.assertNotContains(
            response,
            'Prison 3',
        )

    @responses.activate
    def test_sees_all_prisons(self):
        """
        Test that if the user hasn't specified any prisons in settings, it means that he/she can
        see all prisons so the text 'All prisons' is known in the prison switcher area.
        """
        self._mock_api_responses()
        self.login(
            user_data=self.get_user_data(prisons=[]),
        )
        response = self.client.get(reverse('security:sender_list'))
        self.assertContains(
            response,
            'All prisons',
        )
