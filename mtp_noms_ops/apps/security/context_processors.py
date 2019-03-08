from urllib.parse import urlencode

from django.conf import settings

from .utils import (
    can_see_notifications, can_choose_prisons, is_nomis_api_configured
)


def notifications_available(request):
    return {'notifications_available': can_see_notifications(request.user)}


def nomis_api_available(_):
    return {'nomis_api_available': is_nomis_api_configured()}


def prison_choice_available(request):
    return {
        'prison_choice_available': (
            request.user.is_authenticated and can_choose_prisons(request.user)
        )
    }


def initial_params(request):
    if not request.user_prisons:
        return {}
    return {'initial_params': urlencode([
        ('prison', prison['nomis_id'])
        for prison in request.user_prisons
    ], doseq=True)}


def initial_disbursement_params(request):
    if not request.user_prisons:
        return {}
    return {'initial_disbursement_params': urlencode([
        ('prison', prison['nomis_id'])
        for prison in request.user_prisons
        if not settings.DISBURSEMENT_PRISONS or
        prison['nomis_id'] in settings.DISBURSEMENT_PRISONS
    ], doseq=True)}
