from urllib.parse import urlparse

from mtp_common.api import retrieve_all_pages_for_path
from mtp_common.auth.exceptions import HttpNotFoundError


def filter_list_to_dict(filter_list):
    return {
        searchfilter['field']: searchfilter['value']
        for searchfilter in filter_list
    }


def get_saved_searches(session):
    return retrieve_all_pages_for_path(session, '/searches/')


def populate_new_result_counts(session, saved_searches, delete_invalid=True):
    modified = []
    for saved_search in saved_searches:
        filters = filter_list_to_dict(saved_search['filters'])
        try:
            current_results = session.get(saved_search['endpoint'], params=filters).json()
            new_result_count = current_results['count'] - saved_search['last_result_count']
            saved_search['new_result_count'] = new_result_count if new_result_count > 0 else 0
            modified.append(saved_search)
        except HttpNotFoundError:
            if delete_invalid:
                delete_search(session, saved_search['id'])
    return modified


def get_existing_search(session, path):
    saved_searches = get_saved_searches(session)
    for search in saved_searches:
        if urlparse(search['site_url']).path == path:
            return search
    return None


def save_search(session, description, endpoint, site_url, filters=None, last_result_count=0):
    return session.post('/searches/', json={
        'description': description,
        'endpoint': endpoint,
        'site_url': site_url,
        'filters': [{'field': field, 'value': value} for field, value in (filters or {}).items()],
        'last_result_count': last_result_count
    })


def update_result_count(session, search_id, new_result_count):
    session.patch(
        '/searches/{search_id}/'.format(search_id=search_id),
        json={'last_result_count': new_result_count}
    )


def delete_search(session, search_id):
    session.delete('/searches/{search_id}/'.format(search_id=search_id))
