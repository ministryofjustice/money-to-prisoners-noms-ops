import unittest

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
