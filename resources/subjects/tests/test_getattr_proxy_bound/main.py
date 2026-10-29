"""A slotted proxy that delegates attribute access, as sphinx's translations do.

``sphinx.locale._TranslationProxy`` holds a function and its arguments in
``__slots__`` and resolves them lazily: ``data`` is a property that calls the
function, and ``__getattr__`` forwards anything else to ``self.data``. Reading
an attribute that a slot has not bound yet therefore does not simply raise --
the ``AttributeError`` hands control to ``__getattr__``, which reads ``data``,
which reads the unbound slot again.

A probe only has to read one such attribute to enter that circle. Its own
``try`` catches the eventual ``RecursionError``, so nothing crashes and the run
looks healthy, but every level of the recursion is instrumented subject code
and emits its own events: the trace fills with millions of them and covers
almost nothing.
"""
from collections import UserString


class TranslationProxy(UserString):
    __slots__ = ("_func", "_args")

    def __new__(cls, func, *args):
        if not args:
            return str(func)
        return object.__new__(cls)

    def __getnewargs__(self):
        return (self._func,) + self._args

    def __init__(self, func, *args):
        self._func = func
        self._args = args

    @property
    def data(self):
        return self._func(*self._args)

    def __str__(self):
        return str(self.data)

    def __mod__(self, other):
        return self.data % other

    def __rmod__(self, other):
        return other % self.data

    def __getattr__(self, name):
        if name == "__members__":
            return self.__dir__()
        return getattr(self.data, name)


def translate(word):
    return word.upper()


proxy = TranslationProxy(translate, "hello")
print(str(proxy))
print("%s!" % proxy)
print(proxy.lower())

