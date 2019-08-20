from urllib.parse import urlencode

from django.contrib.auth import REDIRECT_FIELD_NAME

from security import SEARCH_V2_FLAG
from security.forms.object_list import PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE
from security.utils import can_choose_prisons, is_nomis_api_configured


def nomis_api_available(_):
    return {'nomis_api_available': is_nomis_api_configured()}


def prison_choice_available(request):
    return {
        'prison_choice_available': (
            request.user.is_authenticated and can_choose_prisons(request.user)
        )
    }


def initial_params(request):
    user_flags = request.user.user_data.get('flags') or []
    if SEARCH_V2_FLAG in user_flags:
        return {
            'initial_params': urlencode(
                {'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE},
            ),
        }

    if not request.user_prisons:
        return {}

    return {'initial_params': urlencode([
        ('prison', prison['nomis_id'])
        for prison in request.user_prisons
    ], doseq=True)}


def common(_):
    """
    Context Processor for common / core logic, e.g. making some variable available in the templates.
    """
    return {
        'REDIRECT_FIELD_NAME': REDIRECT_FIELD_NAME,
        'PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
    }
