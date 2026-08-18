import enum
from typing import List, Dict, Type

from sflkitlib.events import EventType

import sflkit.language.python.factory as python_factory
from sflkit.analysis.analysis_type import AnalysisObject
from sflkit.language.extract import VariableExtract, ConditionExtract
from sflkit.language.finder import BranchFinder, LoopFinder, FunctionFinder
from sflkit.language.meta import MetaVisitor
from sflkit.language.python.extract import PythonVarExtract, PythonConditionExtract
from sflkit.language.python.finder import (
    PythonFunctionFinder,
    PythonLoopFinder,
    PythonBranchFinder,
)
from sflkit.language.python.visitor import PythonInstrumentation
from sflkit.language.visitor import ASTVisitor

_PYTHON_FACTORIES = {
    EventType.LINE: python_factory.LineEventFactory,
    EventType.BRANCH: python_factory.BranchEventFactory,
    EventType.DEF: python_factory.DefEventFactory,
    EventType.USE: python_factory.UseEventFactory,
    EventType.LOOP_BEGIN: python_factory.LoopBeginEventFactory,
    EventType.LOOP_HIT: python_factory.LoopHitEventFactory,
    EventType.LOOP_END: python_factory.LoopEndEventFactory,
    EventType.FUNCTION_ENTER: python_factory.FunctionEnterEventFactory,
    EventType.FUNCTION_EXIT: python_factory.FunctionExitEventFactor,
    EventType.FUNCTION_ERROR: python_factory.FunctionErrorEventFactory,
    EventType.CONDITION: python_factory.ConditionEventFactory,
    EventType.CONDITION_VALUE: python_factory.ConditionValueEventFactory,
    EventType.LEN: python_factory.LenEventFactory,
    EventType.TEST_START: python_factory.TestStartEventFactory,
    EventType.TEST_END: python_factory.TestEndEventFactory,
    EventType.TEST_LINE: python_factory.TestLineEventFactory,
    EventType.TEST_DEF: python_factory.TestDefEventFactory,
    EventType.TEST_USE: python_factory.TestUseEventFactory,
    EventType.TEST_ASSERT: python_factory.TestAssertEventFactory,
}


def _python_parts(visitor):
    """
    Build the Python backend's pieces.

    :param visitor: Instrumentation visitor, or ``None`` where there is none.
    :returns: Everything a :class:`Language` member exposes besides its
        suffixes.
    """
    return (
        visitor,
        _PYTHON_FACTORIES,
        PythonVarExtract(),
        PythonVarExtract(use=True),
        PythonConditionExtract(),
        PythonFunctionFinder,
        PythonLoopFinder,
        PythonBranchFinder,
    )


def _no_parts():
    """:returns: Empty pieces, for a language with no backend."""
    return (None, dict(), None, None, None, None, None, None)


#: Loaders, defined once so that members sharing one stay aliases of each other.
_PYTHON_LOADER = lambda: _python_parts(PythonInstrumentation)
_PYTHON2_LOADER = lambda: _python_parts(None)


class Language(enum.Enum):
    """
    A supported language and the backend that instruments it.

    A member's backend is built the first time something asks for it, so
    importing this module does not drag in every language's dependencies. Only
    the suffixes are known up front, because that is all the file walker needs
    to decide whether a language is relevant at all.
    """

    def __init__(self, loader, suffixes: List[str]):
        self._loader = loader
        self._parts = None
        self.suffixes = suffixes

    def _load(self):
        """:returns: The backend's pieces, built on first use."""
        if self._parts is None:
            self._parts = self._loader()
        return self._parts

    @property
    def visitor(self) -> Type[ASTVisitor]:
        """The instrumentation visitor."""
        return self._load()[0]

    @property
    def meta_visitors(self) -> Dict[EventType, Type[MetaVisitor]]:
        """Event factories, keyed by event type."""
        return self._load()[1]

    @property
    def var_extract(self) -> VariableExtract:
        """Extractor for defined variables."""
        return self._load()[2]

    @property
    def use_extract(self) -> VariableExtract:
        """Extractor for used variables."""
        return self._load()[3]

    @property
    def condition_extract(self) -> ConditionExtract:
        """Extractor for conditions."""
        return self._load()[4]

    @property
    def function_finder(self) -> FunctionFinder:
        """Finder locating a function in the source."""
        return self._load()[5]

    @property
    def loop_finder(self) -> LoopFinder:
        """Finder locating a loop in the source."""
        return self._load()[6]

    @property
    def branch_finder(self) -> BranchFinder:
        """Finder locating a branch in the source."""
        return self._load()[7]

    def setup(self):
        AnalysisObject.set_finder(
            self.function_finder, self.loop_finder, self.branch_finder
        )

    PYTHON = (_PYTHON_LOADER, ["py"])  # Equals PYTHON3
    PYTHON3 = PYTHON
    PYTHON2 = (_PYTHON2_LOADER, ["py"])
    C = (_no_parts, ["c", "h"])
    # Not wired on this line: the Java backend arrives with its own release.
    JAVA = (_no_parts, ["java"])
