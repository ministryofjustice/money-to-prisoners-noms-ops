from collections import namedtuple
from unittest import mock

from django.http import QueryDict
from django.test import SimpleTestCase
from mtp_common.auth.test_utils import generate_tokens
import responses

from security.forms.base import SecurityForm
from security.tests.utils import mock_empty_response, mock_prison_response


ValidationScenario = namedtuple('ValidationScenario', 'data errors')


class SecurityFormTestCase(SimpleTestCase):
    form_class = None

    def setUp(self):
        super().setUp()
        self.request = mock.MagicMock(
            user=mock.MagicMock(
                token=generate_tokens()
            )
        )
        self.disable_cache = mock.patch('security.models.cache')
        self.disable_cache.start().get.return_value = None

    def tearDown(self):
        self.disable_cache.stop()

    @mock.patch.object(SecurityForm, 'get_object_list_endpoint_path')
    def test_base_security_form(self, get_object_list_endpoint_path):
        if self.form_class:
            return

        # mock no results from API
        get_object_list_endpoint_path.return_value = '/test/'
        expected_data = {'page': 1}

        with responses.RequestsMock() as rsps:
            mock_empty_response(rsps, '/test/')
            form = SecurityForm(self.request, data={})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
            self.assertDictEqual(form.get_query_data(), {})
            self.assertEqual(form.query_string, '')

        with responses.RequestsMock() as rsps:
            mock_empty_response(rsps, '/test/')
            form = SecurityForm(self.request, data={'page': '1'})
            self.assertTrue(form.is_valid())
            self.assertDictEqual(form.cleaned_data, expected_data)
            self.assertListEqual(form.get_object_list(), [])
            self.assertDictEqual(form.get_query_data(), {})
            self.assertEqual(form.query_string, '')

    def test_filtering_by_one_prison(self):
        if not self.form_class:
            return
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data=QueryDict('prison=INP', mutable=True))
        initial_ordering = form['ordering'].initial
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.get_query_data(), {'ordering': initial_ordering, 'prison': ['INP']})
        self.assertEqual(form.query_string, 'ordering=%s&prison=INP' % initial_ordering)

    def test_filtering_by_many_prisons(self):
        if not self.form_class:
            return
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data=QueryDict('prison=IXB&prison=INP', mutable=True))
        initial_ordering = form['ordering'].initial
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.get_query_data(), {'ordering': initial_ordering, 'prison': ['INP', 'IXB']})
        self.assertEqual(form.query_string, 'ordering=%s&prison=INP&prison=IXB' % initial_ordering)

    def test_filtering_by_many_prisons_alternate(self):
        if not self.form_class:
            return
        with responses.RequestsMock() as rsps:
            mock_prison_response(rsps)
            form = self.form_class(self.request, data=QueryDict('prison=IXB,INP,', mutable=True))
        initial_ordering = form['ordering'].initial
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.get_query_data(), {'ordering': initial_ordering, 'prison': ['INP', 'IXB']})
        self.assertEqual(form.query_string, 'ordering=%s&prison=INP&prison=IXB' % initial_ordering)
