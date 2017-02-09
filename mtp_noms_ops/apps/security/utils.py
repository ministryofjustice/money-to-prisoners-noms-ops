import collections
import re


class OrderedSet(collections.MutableSet):
    def __init__(self, iterable=None):
        super().__init__()
        self.item_list = []
        self.item_set = set()
        if iterable:
            self.extend(iterable)

    def __repr__(self):
        return repr(self.item_list)

    def __len__(self):
        return len(self.item_list)

    def __iter__(self):
        return iter(self.item_list)

    def __contains__(self, item):
        item_hash = self.hash_item(item)
        return item_hash in self.item_set

    def add(self, item):
        item_hash = self.hash_item(item)
        if item_hash not in self.item_set:
            self.item_list.append(item)
            self.item_set.add(item_hash)

    def extend(self, iterable):
        for item in iterable:
            self.add(item)

    def discard(self, item):
        item_hash = self.hash_item(item)
        self.item_list.remove(item)
        self.item_set.remove(item_hash)

    def pop_first(self):
        item = self.item_list.pop(0)
        item_hash = self.hash_item(item)
        self.item_set.remove(item_hash)
        return item

    def hash_item(self, item):
        raise NotImplementedError


class NameSet(OrderedSet):
    whitespace = re.compile(r'\s+')
    title_prefixes = {'miss ', 'mrs ', 'mr ', 'dr '}

    def __init__(self, iterable=None, strip_titles=False):
        super().__init__(iterable=iterable)
        self.strip_titles = strip_titles

    def hash_item(self, item):
        name = self.whitespace.sub(' ', item.strip()).lower()
        if self.strip_titles:
            for title_prefix in self.title_prefixes:
                if name.startswith(title_prefix):
                    return name[len(title_prefix):]
        return name
