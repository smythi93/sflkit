"""A property that assigns itself, as astropy's ``Card.comment`` does.

Every probe that reports a variable has to read it, and reading a property runs
the property. When the probe sits inside that property the read re-enters it,
and here the branch it takes does not depend on what the setter writes, so the
re-entry never terminates. The interpreter's C stack dies before Python's
recursion counter trips, so the process aborts outright and the ``try`` around
each probe never gets the chance to catch anything.
"""


class Card:
    def __init__(self):
        self._image = None
        self._comment = None

    @property
    def comment(self):
        if self._image:
            self._comment = "parsed"
            return self._comment
        else:
            self.comment = ""
            return ""

    @comment.setter
    def comment(self, value):
        self._comment = value


class Holder:
    def __init__(self):
        self._items = None

    @property
    def items(self):
        if self._items is None:
            self.items = []
        return self._items

    @items.setter
    def items(self, value):
        self._items = value


print(repr(Card().comment))
print(len(Holder().items))
