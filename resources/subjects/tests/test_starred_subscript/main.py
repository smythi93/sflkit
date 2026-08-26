"""Subscripts built from a tuple with unpacking, as xarray's variable.py does.

``ast.unparse`` drops the parentheses around ``x[(a, *b)]`` and emits
``x[a, *b]``, which is only syntax from Python 3.11. Instrumentation runs on a
recent interpreter while the rewritten sources run on the subject's, so the
regenerated module has to stay within the syntax the subject's Python accepts.
"""


def put(data, indexer, value):
    data[(..., *indexer)] = value
    return data


def take(data, indexer):
    return data[(..., *indexer)]


class Grid:
    def __init__(self):
        self.cells = {}

    def __setitem__(self, key, value):
        self.cells[key] = value

    def __getitem__(self, key):
        return self.cells[key]


grid = Grid()
put(grid, (1, 2), "stored")
print(take(grid, (1, 2)))
