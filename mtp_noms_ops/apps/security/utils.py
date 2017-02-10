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

    def __getitem__(self, index):
        return self.item_list[index]

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
    """
    An ordered set of names: adding a name will not modify it,
    but if a similar one already exists, the new one is not added
    """
    whitespace = re.compile(r'\s+')
    titles = {'miss', 'mrs', 'mr', 'dr'}

    def __init__(self, iterable=None, strip_titles=False):
        self.strip_titles = strip_titles
        super().__init__(iterable=iterable)

    def hash_item(self, item):
        name = self.whitespace.sub(' ', (item or '').strip()).lower()
        if self.strip_titles:
            for title_prefix in (t for title in self.titles for t in ('%s ' % title, '%s. ' % title)):
                if name.startswith(title_prefix):
                    return name[len(title_prefix):]
        return name


class EmailSet(OrderedSet):
    """
    An ordered set of email addresses: adding an email will not modify it,
    but if a similar one already exists, the new one is not added
    """

    def hash_item(self, item):
        return (item or '').strip().lower()
