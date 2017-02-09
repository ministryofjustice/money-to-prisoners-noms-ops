from mtp_common.api import retrieve_all_pages
from mtp_common.auth.api_client import get_connection
from slumber.exceptions import HttpClientError
from slumber.utils import url_join


def get_saved_searches(request):
    searches = []
    client = get_connection(request)
    try:
        searches = retrieve_all_pages(client.searches.get)
        for search in searches:
            filters = {
                searchfilter['field']: searchfilter['value']
                for searchfilter in search['filters']
            }
            endpoint = get_slumber_resource_from_path(client, search['endpoint'])
            current_results = endpoint.get(**filters)
            new_result_count = current_results['count'] - search['last_result_count']
            search['new_result_count'] = new_result_count if new_result_count > 0 else 0
    except HttpClientError:
        pass
    return searches


def get_slumber_resource_from_path(client, path):
    resource = client._get_resource(**client._store)
    return resource(url_override=url_join(resource._store['base_url'], path))
