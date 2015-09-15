from django.core.urlresolvers import reverse
from django.test import SimpleTestCase, RequestFactory

from ..forms import LocationFileUploadForm
from .data import VALID_FILE_PATH


class LocationFileUploadFormTestCase(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_valid_location_file(self):
        with open(VALID_FILE_PATH) as f:
            request = self.factory.post(reverse('location_file_upload'),
                                        {'location_file': f})
        form = LocationFileUploadForm(request.POST, request.FILES, request=request)

        self.assertTrue(form.is_valid())
