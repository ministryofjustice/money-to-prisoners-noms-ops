import enum
import json

from django.core.cache import cache
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from mtp_common.api import retrieve_all_pages_for_path


class PaymentMethod(enum.Enum):
    bank_transfer = _('Bank transfer')
    online = _('Debit card')
    cheque = _('Cheque')


credit_sources = {
    PaymentMethod.bank_transfer.name: PaymentMethod.bank_transfer.value,
    PaymentMethod.online.name: PaymentMethod.online.value,
}
credit_resolutions = {
    'initial': _('Initial'),
    'pending': _('Pending'),
    'manual': _('Requires manual processing'),
    'credited': _('Credited'),
    'refunded': _('Refunded'),
    'failed': _('Failed or rejected'),
}

disbursement_methods = {
    PaymentMethod.bank_transfer.name: PaymentMethod.bank_transfer.value,
    PaymentMethod.cheque.name: PaymentMethod.cheque.value,
}
disbursement_actions = {
    'created': _('Entered'),
    'edited': _('Edited'),
    'rejected': _('Cancelled'),
    'confirmed': _('Confirmed'),
    'sent': _('Sent'),
}
disbursement_resolutions = {
    'pending': _('Waiting for confirmation'),
    'rejected': _('Cancelled'),
    'preconfirmed': _('Confirmed'),
    'confirmed': _('Confirmed'),
    'sent': _('Sent'),
}


class EmailNotifications:
    never = 'never'
    daily = 'daily'


class PrisonList:
    excluded_nomis_ids = {'ZCH'}

    def __init__(self, session, exclude_private_estate=False):
        self.prisons = self.get_prisons(session)

        prison_choices = []
        region_choices = set()
        category_choices = {}
        population_choices = {}
        for prison in self.prisons:
            if prison['nomis_id'] in self.excluded_nomis_ids:
                continue
            if exclude_private_estate and prison.get('private_estate') is True:
                continue
            prison_choices.append((prison['nomis_id'], prison['name']))
            if prison['region']:
                region_choices.add(prison['region'])
            category_choices.update((label['name'], label['description']) for label in prison['categories'])
            population_choices.update((label['name'], label['description']) for label in prison['populations'])

        def sorter(choice):
            return choice[1]

        self.prison_choices = sorted(prison_choices, key=sorter)
        self.region_choices = [(label, label) for label in sorted(region_choices)]
        self.category_choices = sorted(category_choices.items(), key=sorter)
        self.population_choices = sorted(population_choices.items(), key=sorter)

    def get_prisons(self, session):
        prisons = cache.get('PrisonList')
        if prisons is None:
            prisons = retrieve_all_pages_for_path(session, '/prisons/')
            cache.set('PrisonList', prisons, timeout=60 * 15)
        return prisons

    @property
    def mapping(self):
        return {
            prison['nomis_id']: {
                'region': prison['region'] or None,
                'categories': {label['name']: 1 for label in prison['categories']},
                'populations': {label['name']: 1 for label in prison['populations']},
            }
            for prison in self.prisons
            if prison['nomis_id'] not in self.excluded_nomis_ids
        }

    @property
    def mapping_as_json(self):
        return mark_safe(json.dumps(self.mapping, separators=(',', ':')))
