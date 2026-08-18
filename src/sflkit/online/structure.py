"""
Source structure the tracer needs but an event mapping does not record.

Branch events are the reason this module exists. Instrumentation injects a
branch probe as the *first statement of each body*, but records it against the
line of the ``if`` that owns it, so both probes of a branch share one location.
In an instrumented run that is unambiguous, because only the probe in the taken
body executes. A tracer watching the original source sees only "line 6 ran" and
cannot tell the two apart.

What does distinguish them is where execution goes next: entering the then-body
means the next line executed in that frame lies inside it. The bodies' line
ranges are not in the mapping, but they are in the source, and the source is
right there -- the tracer is watching it run. Parsing each mapped file once at
setup therefore recovers exactly the missing bit.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: Nodes that produce a two-sided branch: the body, and everything else.
_BRANCHING = (ast.If, ast.While, ast.For, ast.AsyncFor)


class Span:
    """
    An inclusive range of source lines.

    :ivar start: First line.
    :ivar end: Last line.
    """

    __slots__ = ("start", "end")

    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end

    def __contains__(self, line: int) -> bool:
        return self.start <= line <= self.end

    def __repr__(self):
        return f"Span({self.start}, {self.end})"


class BranchSite:
    """
    A branching statement, as the tracer needs to see it.

    :ivar line: Line of the statement's head, which is where both of its branch
        templates are recorded.
    :ivar then: Span of the body taken when the test holds.
    :ivar orelse: Span of the ``else`` body, or ``None`` when there is none.
        A missing ``else`` is still a branch: instrumentation synthesizes one to
        put its probe in.
    :ivar loop: Whether the statement repeats. A loop head runs once per
        iteration, but the probes hoisted in front of the loop run once, so the
        two groups have to be told apart.
    :ivar targets: Names the loop binds each iteration. Their def and len
        probes sit on the head line but belong to the body.
    """

    __slots__ = ("line", "then", "orelse", "loop", "targets")

    def __init__(
        self,
        line: int,
        then: Span,
        orelse: Optional[Span],
        loop: bool = False,
        targets: Optional[frozenset] = None,
    ):
        self.line = line
        self.then = then
        self.orelse = orelse
        self.loop = loop
        self.targets = targets or frozenset()

    def owns(self, line: int) -> bool:
        """
        :param line: A line number.
        :returns: Whether *line* belongs to this statement, head or body. Used
            to notice that a loop was left, including by ``break``, which skips
            the head entirely.
        """
        return line == self.line or line in self.then

    def taken(self, line: int) -> bool:
        """
        :param line: The next line executed in the frame.
        :returns: Whether the body was entered. Anything that is not inside the
            body means it was not: either the ``else`` ran, or the statement was
            skipped entirely, and both are the sibling branch.
        """
        return line in self.then

    def __repr__(self):
        return f"BranchSite({self.line}, then={self.then}, orelse={self.orelse})"


class TrySite:
    """
    A ``try`` statement.

    Its branch probe is placed at the *end* of the body rather than the start,
    because what it records is "the body completed without raising". It
    therefore fires when execution leaves the body normally.

    :ivar line: Line of the ``try``.
    :ivar body: Span of the protected body.
    :ivar completes: Whether the body can finish by running off its end. When
        it ends in ``return``, ``raise``, ``break`` or ``continue`` the probe
        instrumentation appends after it is unreachable, so no event is due.
    """

    __slots__ = ("line", "body", "completes")

    def __init__(self, line: int, body: Span, completes: bool = True):
        self.line = line
        self.body = body
        self.completes = completes

    def __repr__(self):
        return f"TrySite({self.line}, body={self.body})"


def _span(statements: List[ast.stmt]) -> Span:
    """
    :param statements: A non-empty statement list.
    :returns: The span the list covers.
    """
    first = statements[0]
    last = statements[-1]
    return Span(first.lineno, getattr(last, "end_lineno", None) or last.lineno)


def _targets(node: ast.stmt) -> frozenset:
    """
    :param node: A loop.
    :returns: The names it binds each iteration. ``while`` binds nothing.
    """
    target = getattr(node, "target", None)
    if target is None:
        return frozenset()
    return frozenset(
        child.id for child in ast.walk(target) if isinstance(child, ast.Name)
    )


class SourceStructure:
    """
    Branch and ``try`` structure of one subject, keyed by file and line.

    :ivar branches: ``(file, line)`` to the branching statement there.
    :ivar tries: ``(file, line)`` to the ``try`` statement there.
    """

    def __init__(self):
        self.branches: Dict[Tuple[str, int], BranchSite] = dict()
        self.tries: Dict[Tuple[str, int], TrySite] = dict()

    def add_file(self, name: str, path: Path) -> None:
        """
        Parse *path* and record its branching statements under *name*.

        :param name: The mapping's name for the file.
        :param path: Where to read it from. A file that cannot be read or parsed
            is skipped: the tracer then falls back to emitting no branch events
            for it, which loses data but never invents any.
        """
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError, ValueError):
            return
        for node in ast.walk(tree):
            if isinstance(node, _BRANCHING) and node.body:
                loop = not isinstance(node, ast.If)
                self.branches[(name, node.lineno)] = BranchSite(
                    node.lineno,
                    _span(node.body),
                    _span(node.orelse) if node.orelse else None,
                    loop,
                    _targets(node) if loop else None,
                )
            elif isinstance(node, ast.Try) and node.body:
                self.tries[(name, node.lineno)] = TrySite(
                    node.lineno,
                    _span(node.body),
                    not isinstance(
                        node.body[-1],
                        (ast.Return, ast.Raise, ast.Break, ast.Continue),
                    ),
                )

    def branch(self, file: str, line: int) -> Optional[BranchSite]:
        """
        :param file: Mapping-relative file name.
        :param line: Line of the branching statement.
        :returns: The site, or ``None``.
        """
        return self.branches.get((file, line))

    def try_(self, file: str, line: int) -> Optional[TrySite]:
        """
        :param file: Mapping-relative file name.
        :param line: Line of the ``try``.
        :returns: The site, or ``None``.
        """
        return self.tries.get((file, line))
