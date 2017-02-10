import unittest

from security.templatetags.security import currency, pence, format_sort_code
from security.utils import NameSet, EmailSet


class UtilTestCase(unittest.TestCase):
    def test_currency_formatting(self):
        self.assertEqual(currency(None), None)
        self.assertEqual(currency(''), '')
        self.assertEqual(currency('a'), 'a')
        self.assertEqual(currency(0), '£0.00')
        self.assertEqual(currency(1), '£0.01')
        self.assertEqual(currency(13500), '£135.00')
        self.assertEqual(currency(123500), '£1,235.00')

    def test_pence_formatting(self):
        self.assertEqual(pence(None), None)
        self.assertEqual(pence(''), '')
        self.assertEqual(pence('a'), 'a')
        self.assertEqual(pence(0), '0p')
        self.assertEqual(pence(1), '1p')
        self.assertEqual(pence(99), '99p')
        self.assertEqual(pence(100), '£1.00')

    def test_sort_code_formatting(self):
        self.assertEqual(format_sort_code(None), '—')
        self.assertEqual(format_sort_code(''), '—')
        self.assertEqual(format_sort_code('123456'), '12-34-56')
        self.assertEqual(format_sort_code('1234567'), '1234567')

    def test_name_set(self):
        names = NameSet(['A', 'a', 'A ', ' Aa ', 'John A.', 'MR. JOHN A.'])
        self.assertSequenceEqual(names, ('A', ' Aa ', 'John A.', 'MR. JOHN A.'))
        names.add('JOHN')
        names.add('Mr John')
        self.assertSequenceEqual(names, ('A', ' Aa ', 'John A.', 'MR. JOHN A.', 'JOHN', 'Mr John'))

        names = NameSet(['A', 'a', 'A ', ' Aa ', 'John A.', 'MR. JOHN A.'], strip_titles=True)
        self.assertSequenceEqual(names, ('A', ' Aa ', 'John A.'))
        names.add('JOHN')
        names.add('Mr John')
        self.assertSequenceEqual(names, ('A', ' Aa ', 'John A.', 'JOHN'))

    def test_email_set(self):
        emails = EmailSet(['abc@example.com', 'ABC@EXAMPLE.COM', 'abc@example.co.uk',
                           'abc@example.com ', 'Abc@example.com', ''])
        self.assertSequenceEqual(emails, ('abc@example.com', 'abc@example.co.uk', ''))
