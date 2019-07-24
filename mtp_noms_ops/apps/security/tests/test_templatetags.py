from django.test import SimpleTestCase

from security.templatetags.security import get_split_prison_names


class TestGetSplitPrisonNames(SimpleTestCase):
    """
    Tests for the get_split_prison_names template tag.
    """

    def test_without_need_to_split(self):
        """
        Test that if the split_at value is >= the number of prisons,
        prisons_names includes all prisons and total_renaming is 0.
        """
        tot_prisons = 5

        prisons = [
            {'name': f'Prison {index}'}
            for index in range(tot_prisons)
        ]

        actual_data = get_split_prison_names(prisons, split_at=tot_prisons)
        expected_data = {
            'prison_names': ', '.join(
                [prison['name'] for prison in prisons],
            ),
            'total_remaining': 0,
        }
        self.assertEqual(actual_data, expected_data)

    def test_split(self):
        """
        Test that if the split_at value is < the number of prisons,
        prisons_names includes only the first `split_at` prisons and
        total_renaming is != 0.
        """
        tot_prisons = 5
        split_at = tot_prisons - 1

        prisons = [
            {'name': f'Prison {index}'}
            for index in range(tot_prisons)
        ]

        actual_data = get_split_prison_names(prisons, split_at=split_at)
        expected_data = {
            'prison_names': ', '.join(
                [prison['name'] for prison in prisons[:split_at]],
            ),
            'total_remaining': 1,
        }
        self.assertEqual(actual_data, expected_data)
