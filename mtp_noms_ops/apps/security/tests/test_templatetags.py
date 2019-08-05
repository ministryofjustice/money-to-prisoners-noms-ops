from unittest import mock

from django.test import SimpleTestCase

from security.templatetags.security import (
    extract_best_match,
    get_split_prison_names,
    search_highlight,
    setup_highlight,
)


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


class TestSearchHighlight(SimpleTestCase):
    """
    Tests for the search_highlight template tag.
    """

    def test_returns_default_with_empty_value(self):
        """
        Test that the default value is returned if value is empty.
        """
        # default 'default'
        for value in (None, ''):
            self.assertEqual(
                search_highlight({}, value),
                '',
            )

        # given default
        for value in (None, ''):
            self.assertEqual(
                search_highlight({}, value, default='replacement'),
                'replacement',
            )

    def test_replace(self):
        """
        Test that the matching portion of value is replaced by a span.
        """
        context = {
            'is_search_results': True,
            'form': mock.Mock(
                cleaned_data={
                    'simple_search': 'term1 term2',
                },
            ),
        }

        scenarios = (
            # simple case
            (
                'prefixterm1suffix',
                'prefix<span class="mtp-search-highlight">term1</span>suffix',
            ),
            # uppercase
            (
                'prefixTERM2suffix',
                'prefix<span class="mtp-search-highlight">TERM2</span>suffix',
            ),
            # multiple terms multiple times
            (
                'aterm2 bterm1 cterm2',
                (
                    'a<span class="mtp-search-highlight">term2</span> '
                    'b<span class="mtp-search-highlight">term1</span> '
                    'c<span class="mtp-search-highlight">term2</span>'
                )
            ),
            # non-match
            (
                'prefixtern1suffix',
                'prefixtern1suffix',
            ),
        )

        for value, expected_result in scenarios:
            self.assertEqual(
                search_highlight(context, value),
                expected_result,
            )

    def test_does_not_replace_if_not_on_search_results_page(self):
        """
        Test that if `is_search_results` can't be found in context, the template tag doesn't do anything.
        """
        context = {
            'form': mock.Mock(
                cleaned_data={
                    'simple_search': 'term',
                },
            ),
        }
        self.assertEqual(
            search_highlight(context, 'term'),
            'term',
        )

    def test_does_not_replace_if_form_not_in_context(self):
        """
        Test that if `form` can't be found in context, the template tag doesn't do anything.
        """
        context = {
            'is_search_results': True,
        }
        self.assertEqual(
            search_highlight(context, 'term'),
            'term',
        )

    def test_does_not_replace_if_search_term_is_empty(self):
        """
        Test that if the search term is empty, the template tag doesn't do anything.
        """
        context = {
            'is_search_results': True,
            'form': mock.Mock(
                cleaned_data={
                    'simple_search': '',
                },
            ),
        }
        self.assertEqual(
            search_highlight(context, 'term'),
            'term',
        )

    def test_does_not_replace_if_search_term_not_in_context(self):
        """
        Test that if the search term doesn't exist in context, the template tag doesn't do anything.
        """
        context = {
            'is_search_results': True,
            'form': mock.Mock(
                cleaned_data={},
            ),
        }
        self.assertEqual(
            search_highlight(context, 'term'),
            'term',
        )


class TestSetupHighlight(SimpleTestCase):
    """
    Tests for the setup_highlight template tag.
    """

    def test_caches_regex(self):
        """
        Test that the compiled re is cached so that can be used in subsequent highlight calls.
        """
        context = {
            'is_search_results': True,
            'form': mock.Mock(
                cleaned_data={
                    'simple_search': 'term',
                },
            ),
        }
        setup_highlight(context)

        assert '_search_terms_re' in context


class TestExtractBestMatch(SimpleTestCase):
    """
    Tests for the extract_best_match template tag.
    """
    def test_match(self):
        """
        Test that the template tag returns the first item in the list that matches one of the words
        in the search term.
        """
        context = {
            'is_search_results': True,
            'form': mock.Mock(
                cleaned_data={
                    'simple_search': 'tem1 term2',
                },
            ),
        }
        self.assertDictEqual(
            extract_best_match(context, ['first', 'second with term2', 'term1']),
            {
                'item': 'second with term2',
                'total_remaining': 2,
            },
        )

    def test_no_match(self):
        """
        Test that the template tag returns the first item in the list if none of them matches
        the search term.
        """
        context = {
            'is_search_results': True,
            'form': mock.Mock(
                cleaned_data={
                    'simple_search': 'tem1 term2',
                },
            ),
        }
        self.assertDictEqual(
            extract_best_match(context, ['first']),
            {
                'item': 'first',
                'total_remaining': 0,
            },
        )

    def test_with_falsy_value(self):
        """
        Test that if the input value is falsy the template tag returns (None, 0).
        """
        for value in (None, []):
            self.assertDictEqual(
                extract_best_match({}, value),
                {
                    'item': None,
                    'total_remaining': 0,
                },
            )

    def test_when_not_on_search_results_page(self):
        """
        Test that if `is_search_results` can't be found in context, the template tag returns
        the first item as best match.
        """
        self.assertDictEqual(
            extract_best_match({}, ['first', 'second']),
            {
                'item': 'first',
                'total_remaining': 1,
            },
        )

    def test_when_search_term_is_empty(self):
        """
        Test that if the search term is empty, the template tag returns the first item as best match.
        """
        context = {
            'is_search_results': True,
            'form': mock.Mock(
                cleaned_data={
                    'simple_search': '',
                },
            ),
        }
        self.assertDictEqual(
            extract_best_match(context, ['first', 'second']),
            {
                'item': 'first',
                'total_remaining': 1,
            },
        )
