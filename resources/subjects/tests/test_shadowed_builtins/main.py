"""A subject that rebinds the builtins the probes rely on.

Real projects do this. ``_pytest.outcomes`` binds ``Exception`` in a Protocol's
class body so that ``skip.Exception`` names the exception a helper raises, which
turned a probe's ``except Exception`` into ``except None`` and made importing
the package fail outright.
"""


class ShadowsInClassBody:
    Exception = None
    len = None
    type = None
    isinstance = None
    property = None
    hasattr = None

    def method(self, x):
        y = x + 1
        return y


def shadows_in_function(x):
    Exception = None
    len = None
    type = None
    isinstance = None
    property = None
    hasattr = None
    y = [x]
    if y:
        return Exception is None and len is None
    return False


print(ShadowsInClassBody().method(1))
print(shadows_in_function(2))
