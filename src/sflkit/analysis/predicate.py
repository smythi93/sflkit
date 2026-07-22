import enum
from abc import ABC
from typing import Tuple, Callable, Optional, List, Type, Any

from sflkitlib.events import EventType
from sflkitlib.events.event import (
    BranchEvent,
    FunctionExitEvent,
    DefEvent,
    Event,
    ConditionEvent,
)

from sflkit.analysis.analysis_type import (
    AnalysisType,
    EvaluationResult,
    MetaEvent,
    AnalysisObject,
)
from sflkit.analysis.spectra import Spectrum
from sflkit.analysis.suggestion import Suggestion, Location
from sflkit.events.event_file import EventFile
from sflkit.model.scope import Scope


class Predicate(Spectrum, ABC):
    def __init__(self, file, line):
        super().__init__(file, line)
        self.true_relevant = 0
        self.false_relevant = 0
        self.true_irrelevant = 0
        self.false_irrelevant = 0
        self.fail_true = 0
        self.fail_false = 0
        self.context = 1
        self.increase_true = 0
        self.increase_false = 0
        self.total_hits = dict()

    def serialize(self):
        default = super().serialize()
        default["true_relevant"] = self.true_relevant
        default["false_relevant"] = self.false_relevant
        default["true_irrelevant"] = self.true_irrelevant
        default["false_irrelevant"] = self.false_irrelevant
        default["fail_true"] = self.fail_true
        default["fail_false"] = self.fail_false
        default["context"] = self.context
        default["increase_true"] = self.increase_true
        default["increase_false"] = self.increase_false
        return default

    def _deserialize(self, s: dict):
        super()._deserialize(s)
        self.true_relevant = s["true_relevant"]
        self.false_relevant = s["false_relevant"]
        self.true_irrelevant = s["true_irrelevant"]
        self.false_irrelevant = s["false_irrelevant"]
        self.fail_true = s["fail_true"]
        self.fail_false = s["fail_false"]
        self.context = s["context"]
        self.increase_true = s["increase_true"]
        self.increase_false = s["increase_false"]

    @staticmethod
    def default_evaluation() -> EvaluationResult:
        return EvaluationResult.UNOBSERVED

    def get_last_evaluation(
        self, id_: int, thread_id: Optional[int] = None
    ) -> EvaluationResult:
        if id_ in self.last_evaluation and thread_id in self.last_evaluation[id_]:
            return self.last_evaluation[id_][thread_id]
        return self.default_evaluation()

    def finalize(self, passed: list[EventFile], failed: list[EventFile]):
        super().finalize(passed, failed)
        for p in passed:
            if p in self.hits:
                if self._check_hits(p):
                    self.true_irrelevant_observed()
                else:
                    self.false_irrelevant_observed()
        for f in failed:
            if f in self.hits:
                if self._check_hits(f):
                    self.true_relevant_observed()
                else:
                    self.false_relevant_observed()

    def hit(self, id_, event: Event, scope: Scope = None):
        if id_ not in self.total_hits:
            self.total_hits[id_] = dict()
        if event.thread_id not in self.total_hits[id_]:
            self.total_hits[id_][event.thread_id] = 0
        if id_ not in self.hits:
            self.hits[id_] = dict()
            self.last_evaluation[id_] = dict()
        if event.thread_id not in self.hits[id_]:
            self.hits[id_][event.thread_id] = 0
        self.total_hits[id_][event.thread_id] += 1
        if self._evaluate_predicate(event, scope):
            self.hits[id_][event.thread_id] += 1
            self.last_evaluation[id_][event.thread_id] = EvaluationResult.TRUE
        else:
            self.last_evaluation[id_][event.thread_id] = EvaluationResult.FALSE

    def get_metric(self, metric: Callable = None, use_weight: bool = False):
        if metric is None:
            metric = Predicate.IncreaseTrue
        return super().get_metric(metric, use_weight=use_weight)

    def _evaluate_predicate(self, event: Event, scope: Scope):
        return False

    def true_relevant_observed(self):
        self.true_relevant += 1

    def true_irrelevant_observed(self):
        self.true_irrelevant += 1

    def false_relevant_observed(self):
        self.false_relevant += 1

    def false_irrelevant_observed(self):
        self.false_irrelevant += 1

    def Fail(self) -> Tuple[float, float]:
        try:
            self.fail_true = self.true_relevant / (
                self.true_relevant + self.true_irrelevant
            )
        except ZeroDivisionError:
            pass
        try:
            self.fail_false = self.false_relevant / (
                self.false_relevant + self.false_irrelevant
            )
        except ZeroDivisionError:
            pass
        return self.fail_true, self.fail_false

    def Contex(self) -> float:
        try:
            self.context = (self.true_relevant + self.false_relevant) / (
                self.true_relevant
                + self.true_irrelevant
                + self.false_relevant
                + self.false_irrelevant
            )
        except ZeroDivisionError:
            pass
        return self.context

    def IncreaseTrue(self) -> float:
        return self.increase_true

    def IncreaseFalse(self) -> float:
        return self.increase_false

    def Increase(self) -> Tuple[float, float]:
        self.increase_true = self.fail_true - self.context
        self.increase_false = self.fail_false - self.context
        return self.increase_true, self.increase_false

    def calculate(self):
        self.Fail()
        self.Contex()
        self.Increase()


class Branch(Predicate):
    def __init__(self, event: BranchEvent, then: bool = True, then_id: int = None):
        super().__init__(event.file, event.line)
        if then_id is not None:
            self.then_id = then_id
        else:
            self.then_id = event.then_id if then else event.else_id
        self.then = then

    def __hash__(self):
        return hash(
            (self.file, self.line, self.then_id, self.then, self.analysis_type())
        )

    def __eq__(self, other):
        return (
            isinstance(other, Branch)
            and self.file == other.file
            and self.line == other.line
            and self.then_id == other.then_id
            and self.then == other.then
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["then_id"] = self.then_id
        default["then"] = self.then
        return default

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "then_id",
                "then",
            ]
        )
        assert s["type"] == AnalysisType.BRANCH.value
        analysis_object = Branch(
            MetaEvent(
                s["file"],
                s["line"],
                then_id=s["then_id"],
                else_id=None,
            ),
            then=s["then"],
            then_id=s["then_id"],
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type() -> AnalysisType:
        return AnalysisType.BRANCH

    @staticmethod
    def events():
        return [EventType.BRANCH]

    def hit(self, id_, event: BranchEvent, scope: Scope = None):
        if id_ not in self.total_hits:
            self.total_hits[id_] = dict()
        if event.thread_id not in self.total_hits[id_]:
            self.total_hits[id_][event.thread_id] = 0
        if id_ not in self.hits:
            self.hits[id_] = dict()
            self.last_evaluation[id_] = dict()
        if event.thread_id not in self.hits[id_]:
            self.hits[id_][event.thread_id] = 0
        self.total_hits[id_][event.thread_id] += 1
        if event.then_id == self.then_id:
            self.hits[id_][event.thread_id] += 1
            self.last_evaluation[id_][event.thread_id] = EvaluationResult.TRUE
        else:
            self.last_evaluation[id_][event.thread_id] = EvaluationResult.FALSE

    def get_suggestion(
        self, metric: Callable = None, base_dir: str = "", use_weight: bool = False
    ):
        if metric == Predicate.IncreaseFalse:
            finder = self.branch_finder(self.file, self.line, not self.then)
        else:
            finder = self.branch_finder(self.file, self.line, self.then)
        return Suggestion(
            [Location(self.file, line) for line in finder.get_locations(base_dir)],
            self.get_metric(metric, use_weight=use_weight),
        )

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{'then' if self.then else 'else'}:{self.then_id}"


class Comp(enum.Enum):
    LT = "<"
    LE = "<="
    EQ = "=="
    GE = ">="
    GT = ">"
    NE = "!="

    def evaluate(self, x, y):
        if self == Comp.LT:
            return x < y
        elif self == Comp.LE:
            return x <= y
        elif self == Comp.EQ:
            return x == y
        elif self == Comp.GE:
            return x >= y
        elif self == Comp.GT:
            return x > y
        elif self == Comp.NE:
            return x != y
        else:
            raise ValueError(f"Unknown comparison operator: {self}")

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class Comparison(Predicate, ABC):
    def __init__(self, file, line, op: Comp):
        super().__init__(file, line)
        self.op = op

    def serialize(self):
        default = super().serialize()
        default["op"] = self.op.value
        return default

    @staticmethod
    def events():
        return [
            EventType.DEF,
            EventType.FUNCTION_ENTER,
            EventType.FUNCTION_EXIT,
            EventType.FUNCTION_ERROR,
        ]

    def _evaluate_predicate(self, event: Event, scope_: Scope) -> bool:
        return self._compare(self._get_first(scope_), self._get_second(scope_))

    def _compare(self, first, second) -> bool:
        return self.op.evaluate(first, second)

    def _get_first(self, scope_: Scope):
        return 0

    def _get_second(self, scope_: Scope):
        return 0


class ScalarPair(Comparison):
    def __init__(self, event: DefEvent, op: Comp, var: str):
        super().__init__(event.file, event.line, op)
        self.var1 = event.var
        self.var2 = var

    def __hash__(self):
        return hash(
            (self.file, self.line, self.var1, self.var2, self.op, self.analysis_type())
        )

    def __eq__(self, other):
        return (
            isinstance(other, ScalarPair)
            and self.file == other.file
            and self.line == other.line
            and self.var1 == other.var1
            and self.var2 == other.var2
            and self.op == other.op
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["var1"] = self.var1
        default["var2"] = self.var2
        return default

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "var1",
                "var2",
                "op",
            ]
        )
        assert s["type"] == AnalysisType.SCALAR_PAIR.value
        analysis_object = ScalarPair(
            MetaEvent(s["file"], s["line"], var=s["var1"]),
            Comp(s["op"]),
            s["var2"],
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.SCALAR_PAIR

    def _get_first(self, scope_: Scope):
        return scope_.value(self.var1)

    def _get_second(self, scope_: Scope):
        return scope_.value(self.var2)

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.var1}{self.op}{self.var2}"


class VariablePredicate(Comparison):
    def __init__(self, event: DefEvent, op: Comp):
        super().__init__(event.file, event.line, op)
        self.var = event.var

    def __hash__(self):
        return hash((self.file, self.line, self.var, self.op, self.analysis_type()))

    def __eq__(self, other):
        return (
            isinstance(other, VariablePredicate)
            and self.file == other.file
            and self.line == other.line
            and self.var == other.var
            and self.op == other.op
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "var",
                "op",
            ]
        )
        assert s["type"] == AnalysisType.VARIABLE.value
        analysis_object = VariablePredicate(
            MetaEvent(s["file"], s["line"], var=s["var"]),
            Comp(s["op"]),
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.VARIABLE

    @staticmethod
    def events():
        return [
            EventType.DEF,
        ]

    def _get_first(self, scope: Scope):
        return scope.value(self.var)

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.var}{self.op}0"


class NonePredicate(Comparison):
    def __init__(self, event: DefEvent):
        super().__init__(event.file, event.line, Comp.EQ)
        self.var = event.var

    def __hash__(self):
        return hash((self.file, self.line, self.var, self.analysis_type()))

    def __eq__(self, other):
        return (
            isinstance(other, NonePredicate)
            and self.file == other.file
            and self.line == other.line
            and self.var == other.var
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "var",
                "op",
            ]
        )
        assert s["type"] == AnalysisType.NONE.value
        analysis_object = NonePredicate(MetaEvent(s["file"], s["line"], var=s["var"]))
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.NONE

    @staticmethod
    def events():
        return [
            EventType.DEF,
        ]

    def _get_first(self, scope: Scope):
        return scope.value(self.var)

    def _get_second(self, scope: Scope):
        return None

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.var}"


class ReturnPredicate(Comparison):
    def __init__(self, event: FunctionExitEvent, op: Comp, value: Optional[int] = 0):
        super().__init__(event.file, event.line, op)
        self.function = event.function
        self.value = value

    def __hash__(self):
        return hash(
            (
                self.file,
                self.line,
                self.function,
                self.value,
                self.op,
                self.analysis_type(),
            )
        )

    def __eq__(self, other):
        return (
            isinstance(other, ReturnPredicate)
            and self.file == other.file
            and self.line == other.line
            and self.function == other.function
            and self.value == other.value
            and self.op == other.op
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["function"] = self.function
        if isinstance(self.value, bytes):
            default["value"] = self.value.decode("utf-8")
            default["bytes"] = True
        else:
            default["value"] = self.value
            default["bytes"] = False
        return default

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "function",
                "value",
                "op",
                "bytes",
            ]
        )
        assert s["type"] == AnalysisType.RETURN.value
        analysis_object = ReturnPredicate(
            MetaEvent(s["file"], s["line"], function=s["function"]),
            Comp(s["op"]),
            s["value"].encode("utf-8") if s["bytes"] else s["value"],
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.RETURN

    @staticmethod
    def events():
        return [
            EventType.FUNCTION_ENTER,
            EventType.FUNCTION_EXIT,
            EventType.FUNCTION_ERROR,
        ]

    def _get_first(self, scope: Scope):
        return scope.value(self.function)

    def _get_second(self, scope: Scope):
        return self.value

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.function}{self.op}{self.value}"


class EmptyStringPredicate(Comparison):
    def __init__(self, event: DefEvent):
        super().__init__(event.file, event.line, Comp.EQ)
        self.var = event.var

    def __hash__(self):
        return hash((self.file, self.line, self.var, self.analysis_type()))

    def __eq__(self, other):
        return (
            isinstance(other, EmptyStringPredicate)
            and self.file == other.file
            and self.line == other.line
            and self.var == other.var
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "var",
                "op",
            ]
        )
        assert s["type"] == AnalysisType.EMPTY_STRING.value
        analysis_object = EmptyStringPredicate(
            MetaEvent(s["file"], s["line"], var=s["var"])
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.EMPTY_STRING

    @staticmethod
    def events():
        return [
            EventType.DEF,
        ]

    def _get_first(self, scope: Scope):
        return scope.value(self.var)

    def _get_second(self, scope: Scope):
        return ""

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.var}"


class EmptyBytesPredicate(Comparison):
    def __init__(self, event: DefEvent):
        super().__init__(event.file, event.line, Comp.EQ)
        self.var = event.var

    def __hash__(self):
        return hash((self.file, self.line, self.var, self.analysis_type()))

    def __eq__(self, other):
        return (
            isinstance(other, EmptyBytesPredicate)
            and self.file == other.file
            and self.line == other.line
            and self.var == other.var
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "var",
                "op",
            ]
        )
        assert s["type"] == AnalysisType.EMPTY_BYTES.value
        analysis_object = EmptyBytesPredicate(
            MetaEvent(s["file"], s["line"], var=s["var"])
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.EMPTY_BYTES

    @staticmethod
    def events():
        return [
            EventType.DEF,
        ]

    def _get_first(self, scope: Scope):
        return scope.value(self.var)

    def _get_second(self, scope: Scope):
        return b""

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.var}"


class FunctionPredicate(Predicate, ABC):
    def __init__(self, file, line, var: str, predicate: Callable[[Any], bool]):
        super().__init__(file, line)
        self.var = var
        self.predicate = predicate

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    @staticmethod
    def events():
        return [
            EventType.DEF,
        ]

    def _evaluate_predicate(self, event: Event, scope: Scope):
        value = scope.value(self.var)
        return isinstance(value, str) and self.predicate(scope.value(self.var))


class IsAsciiPredicate(FunctionPredicate):
    def __init__(self, event: DefEvent):
        super().__init__(event.file, event.line, event.var, str.isascii)

    def __hash__(self):
        return hash((self.file, self.line, self.var, self.analysis_type()))

    def __eq__(self, other):
        return (
            isinstance(other, IsAsciiPredicate)
            and self.file == other.file
            and self.line == other.line
            and self.var == other.var
            and self.analysis_type() == other.analysis_type()
        )

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "var",
            ]
        )
        assert s["type"] == AnalysisType.ASCII_STRING.value
        analysis_object = IsAsciiPredicate(
            MetaEvent(s["file"], s["line"], var=s["var"])
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.ASCII_STRING

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.var}"


class ContainsDigitPredicate(FunctionPredicate):
    def __init__(self, event: DefEvent):
        super().__init__(event.file, event.line, event.var, self._contains_digit)

    def __hash__(self):
        return hash((self.file, self.line, self.var, self.analysis_type()))

    def __eq__(self, other):
        return (
            isinstance(other, ContainsDigitPredicate)
            and self.file == other.file
            and self.line == other.line
            and self.var == other.var
            and self.analysis_type() == other.analysis_type()
        )

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "var",
            ]
        )
        assert s["type"] == AnalysisType.DIGIT_STRING.value
        analysis_object = ContainsDigitPredicate(
            MetaEvent(s["file"], s["line"], var=s["var"])
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def _contains_digit(s):
        return any(c.isdigit() for c in s)

    @staticmethod
    def analysis_type():
        return AnalysisType.DIGIT_STRING

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.var}"


class ContainsSpecialPredicate(FunctionPredicate):
    def __init__(self, event: DefEvent):
        super().__init__(event.file, event.line, event.var, self._contain_special)

    def __hash__(self):
        return hash((self.file, self.line, self.var, self.analysis_type()))

    def __eq__(self, other):
        return (
            isinstance(other, ContainsSpecialPredicate)
            and self.file == other.file
            and self.line == other.line
            and self.var == other.var
            and self.analysis_type() == other.analysis_type()
        )

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "var",
            ]
        )
        assert s["type"] == AnalysisType.SPECIAL_STRING.value
        analysis_object = ContainsSpecialPredicate(
            MetaEvent(s["file"], s["line"], var=s["var"])
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def _contain_special(s):
        return not s.isalnum()

    @staticmethod
    def analysis_type():
        return AnalysisType.SPECIAL_STRING

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.var}"


class Condition(Predicate):
    def __init__(self, file: str, line: int, condition: str, negate: bool = False):
        super().__init__(file, line)
        self.condition = condition
        self.negate = negate

    def __hash__(self):
        return hash(
            (self.file, self.line, self.condition, self.negate, self.analysis_type())
        )

    def __eq__(self, other):
        return (
            isinstance(other, Condition)
            and self.file == other.file
            and self.line == other.line
            and self.condition == other.condition
            and self.negate == other.negate
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["condition"] = self.condition
        default["negate"] = self.negate
        return default

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "condition",
                "negate",
            ]
        )
        assert s["type"] == AnalysisType.CONDITION.value
        analysis_object = Condition(s["file"], s["line"], s["condition"], s["negate"])
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.CONDITION

    @staticmethod
    def events():
        return [EventType.CONDITION]

    def hit(self, id_, event: ConditionEvent, scope: Scope = None):
        if id_ not in self.total_hits:
            self.total_hits[id_] = dict()
        if event.thread_id not in self.total_hits[id_]:
            self.total_hits[id_][event.thread_id] = 0
        if id_ not in self.hits:
            self.hits[id_] = dict()
            self.last_evaluation[id_] = dict()
        if event.thread_id not in self.hits[id_]:
            self.hits[id_][event.thread_id] = 0
            self.last_evaluation[id_][event.thread_id] = EvaluationResult.TRUE
        self.total_hits[id_][event.thread_id] += 1
        if (self.negate and not event.value) or (not self.negate and event.value):
            self.hits[id_][event.thread_id] += 1
            self.last_evaluation[id_][event.thread_id] = EvaluationResult.TRUE
        else:
            self.last_evaluation[id_][event.thread_id] = EvaluationResult.FALSE

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.condition}"


class FunctionErrorPredicate(Predicate):
    def __init__(self, file, line, function):
        super().__init__(file, line)
        self.function = function

    def __hash__(self):
        return hash((self.file, self.line, self.function, self.analysis_type()))

    def __eq__(self, other):
        return (
            isinstance(other, FunctionErrorPredicate)
            and self.file == other.file
            and self.line == other.line
            and self.function == other.function
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["function"] = self.function
        return default

    @staticmethod
    def deserialize(s: dict) -> "AnalysisObject":
        assert all(
            p in s
            for p in [
                "file",
                "line",
                "passed",
                "passed_observed",
                "passed_not_observed",
                "failed",
                "failed_observed",
                "failed_not_observed",
                "type",
                "true_relevant",
                "false_relevant",
                "true_irrelevant",
                "false_irrelevant",
                "fail_true",
                "fail_false",
                "context",
                "increase_true",
                "increase_false",
                "function",
            ]
        )
        assert s["type"] == AnalysisType.FUNCTION_ERROR.value
        analysis_object = FunctionErrorPredicate(s["file"], s["line"], s["function"])
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type() -> AnalysisType:
        return AnalysisType.FUNCTION_ERROR

    @staticmethod
    def events() -> List[Type]:
        return [
            EventType.FUNCTION_ENTER,
            EventType.FUNCTION_ERROR,
            EventType.FUNCTION_EXIT,
        ]

    def _evaluate_predicate(self, event: Event, scope: Scope):
        return event.event_type == EventType.FUNCTION_ERROR

    def get_suggestion(
        self, metric: Callable = None, base_dir: str = "", use_weight: bool = False
    ):
        finder = self.function_finder(self.file, self.line, self.function)
        return Suggestion(
            [Location(self.file, line) for line in finder.get_locations(base_dir)],
            self.get_metric(metric, use_weight=use_weight),
        )

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.function}:{self.line}"
