from typing import List


class Location(object):
    # A location is identified by its file and line, and is used as a dictionary
    # key over and over again while a Rank is built, so the hash is computed once
    # here. Neither attribute may change after construction.
    __slots__ = ("file", "line", "_hash")

    def __init__(self, file: str, line: int):
        self.file = file
        self.line = line
        self._hash = hash((file, line))

    def __repr__(self):
        return f"{self.file}:{self.line}"

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return (
            isinstance(other, Location)
            and other.line == self.line
            and other.file == self.file
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self._hash


class Suggestion(object):
    __slots__ = ("lines", "suspiciousness")

    def __init__(self, lines: List[Location], suspiciousness: float):
        self.lines = lines
        self.suspiciousness = suspiciousness

    def __repr__(self):
        return f"{self.lines}:{self.suspiciousness}"

    def __str__(self):
        return repr(self)

    # Comparisons accept a suggestion as well as a plain number. Two suggestions
    # used to be compared by bouncing through the mirrored operator on the other
    # one, which cost two Python calls for every comparison in every sort.
    def __lt__(self, other):
        if isinstance(other, Suggestion):
            return self.suspiciousness < other.suspiciousness
        return other > self.suspiciousness

    def __gt__(self, other):
        if isinstance(other, Suggestion):
            return self.suspiciousness > other.suspiciousness
        return other < self.suspiciousness

    def __le__(self, other):
        if isinstance(other, Suggestion):
            return self.suspiciousness <= other.suspiciousness
        return other >= self.suspiciousness

    def __ge__(self, other):
        if isinstance(other, Suggestion):
            return self.suspiciousness >= other.suspiciousness
        return other <= self.suspiciousness

    def __len__(self):
        return len(self.lines)
