import base64
import logging

from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.utils.cache import patch_cache_control
from mtp_common.nomis import can_access_nomis, get_photograph_data, get_location
from requests.exceptions import RequestException


logger = logging.getLogger('mtp')


def prisoner_image_view(request, prisoner_number):
    if can_access_nomis() and prisoner_number:
        try:
            b64data = get_photograph_data(prisoner_number)
            if b64data:
                response = HttpResponse(
                    base64.b64decode(b64data), content_type='image/jpeg'
                )
                patch_cache_control(response, private=True, max_age=2592000)
                return response
        except RequestException:
            logger.warning('Could not load image for %(prisoner_number)s', {'prisoner_number': prisoner_number})
    if request.GET.get('ratio') == '2x':
        return HttpResponseRedirect(staticfiles_storage.url('images/placeholder-image@2x.png'))
    else:
        return HttpResponseRedirect(staticfiles_storage.url('images/placeholder-image.png'))


def prisoner_nomis_info_view(request, prisoner_number):
    response_data = {}
    if can_access_nomis() and prisoner_number:
        try:
            location = get_location(prisoner_number)
            if 'housing_location' in location:
                housing = location['housing_location']
                if housing['levels']:
                    # effectively drops prison code prefix from description
                    response_data['housing_location'] = '-'.join(
                        level['value'] for level in housing['levels']
                    )
                else:
                    response_data['housing_location'] = housing['description']
        except RequestException:
            logger.warning('Could not load location for %(prisoner_number)s', {'prisoner_number': prisoner_number})
    response = JsonResponse(response_data)
    patch_cache_control(response, private=True, max_age=3600)
    return response
