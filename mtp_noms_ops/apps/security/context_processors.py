from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.utils.translation import gettext

from security.forms.object_list import PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE
from security.utils import can_choose_prisons


def prison_choice_available(request):
    return {
        'prison_choice_available': (
            request.user.is_authenticated and can_choose_prisons(request.user)
        )
    }


def initial_params(_):
    return {
        'initial_params': urlencode(
            {'prison_selector': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE},
        ),
    }


def common(request):
    if request.can_access_prisoner_location and not request.can_access_security:
        proposition_title = gettext('Prisoner location admin')
    else:
        proposition_title = gettext('Prisoner money intelligence')
    return {
        'proposition_title': proposition_title,
        'footer_feedback_link': settings.FOOTER_FEEDBACK_LINK,
        'REDIRECT_FIELD_NAME': REDIRECT_FIELD_NAME,
        'PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE': PRISON_SELECTOR_USER_PRISONS_CHOICE_VALUE,
        'DPS': settings.DPS,
    }
