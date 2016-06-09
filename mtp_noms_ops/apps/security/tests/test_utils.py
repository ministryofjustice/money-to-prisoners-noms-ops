import unittest

from mtp_noms_ops.view_utils import make_page_range
from security.templatetags.security import currency, format_sort_code


class UtilTestCase(unittest.TestCase):
    def test_currency_formatting(self):
        self.assertEqual(currency(None), '')
        self.assertEqual(currency(0), '0.00')
        self.assertEqual(currency(1), '0.01')
        self.assertEqual(currency(13500), '135.00')
        self.assertEqual(currency(123500), '1,235.00')

    def test_sort_code_formatting(self):
        self.assertEqual(format_sort_code(None), '')
        self.assertEqual(format_sort_code(''), '')
        self.assertEqual(format_sort_code('123456'), '12-34-56')
        self.assertEqual(format_sort_code('1234567'), '1234567')

    def test_page_range(self):
        self.assertSequenceEqual(make_page_range(1, 1), [1])
        self.assertSequenceEqual(make_page_range(1, 2), [1, 2])
        self.assertSequenceEqual(make_page_range(2, 2), [1, 2])
        self.assertSequenceEqual(make_page_range(1, 6), range(1, 7))
        self.assertSequenceEqual(make_page_range(5, 6), range(1, 7))
        self.assertSequenceEqual(make_page_range(1, 7), [1, 2, 3, None, 5, 6, 7])
        self.assertSequenceEqual(make_page_range(4, 7), [1, 2, 3, 4, 5, 6, 7])
        self.assertSequenceEqual(make_page_range(5, 7), [1, 2, 3, 4, 5, 6, 7])
        self.assertSequenceEqual(make_page_range(7, 7), [1, 2, 3, None, 5, 6, 7])
        self.assertSequenceEqual(make_page_range(7, 10), [1, 2, 3, None, 5, 6, 7, 8, 9, 10])
        self.assertSequenceEqual(make_page_range(7, 100), [1, 2, 3, None, 5, 6, 7, 8, 9, None, 98, 99, 100])
