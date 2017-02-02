import json

from django.utils.safestring import mark_safe
from mtp_common.api import retrieve_all_pages


class PrisonList:
    def __init__(self, client):
        self.prisons = retrieve_all_pages(client.prisons.get)

        prison_choices = []
        region_choices = set()
        category_choices = {}
        population_choices = {}
        for prison in self.prisons:
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

    @property
    def mapping(self):
        return {
            prison['nomis_id']: {
                'region': prison['region'] or None,
                'categories': {label['name']: 1 for label in prison['categories']},
                'populations': {label['name']: 1 for label in prison['populations']},
            }
            for prison in self.prisons
        }

    @property
    def mapping_as_json(self):
        return mark_safe(json.dumps(self.mapping, separators=(',', ':')))
