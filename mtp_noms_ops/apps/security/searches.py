from mtp_common.api import retrieve_all_pages
from slumber.utils import url_join


def filter_list_to_dict(filter_list):
    return {
        searchfilter['field']: searchfilter['value']
        for searchfilter in filter_list
    }


def get_saved_searches(client):
    return retrieve_all_pages(client.searches.get)


def populate_new_result_count(client, saved_search):
    filters = filter_list_to_dict(saved_search['filters'])
    endpoint = get_slumber_resource_from_path(client, saved_search['endpoint'])
    current_results = endpoint.get(**filters)
    new_result_count = current_results['count'] - saved_search['last_result_count']
    saved_search['new_result_count'] = new_result_count if new_result_count > 0 else 0
    return saved_search


def get_existing_search(client, path):
    saved_searches = get_saved_searches(client)
    for search in saved_searches:
        if search['site_url'] == path:
            return search
    return None


def get_slumber_resource_from_path(client, path):
    resource = client._get_resource(**client._store)
    return resource(url_override=url_join(resource._store['base_url'], path))


def save_search(client, description, endpoint, site_url, filters=[], last_result_count=0):
    return client.searches.post({
        'description': description,
        'endpoint': endpoint,
        'site_url': site_url,
        'filters': [{'field': field, 'value': filters[field]} for field in filters],
        'last_result_count': last_result_count
    })


def update_result_count(client, search_id, new_result_count):
    client.searches(search_id).patch({'last_result_count': new_result_count})


def delete_search(client, search_id):
    client.searches(search_id).delete()
