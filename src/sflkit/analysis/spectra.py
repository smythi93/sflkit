from abc import ABC
from typing import Callable, Optional, Dict

import numpy

from sflkit.analysis.analysis_type import (
    AnalysisObject,
    AnalysisType,
    EvaluationResult,
    MetaEvent,
)
from sflkit.analysis.suggestion import Suggestion, Location
from sflkit.events.event_file import EventFile
from sflkit.model.scope import Scope
from sflkitlib.events import EventType
from sflkitlib.events.event import (
    LineEvent,
    FunctionEnterEvent,
    LoopEndEvent,
    LoopBeginEvent,
    LoopHitEvent,
    DefEvent,
    UseEvent,
    LenEvent,
)


class Spectrum(AnalysisObject, ABC):
    def __init__(
        self,
        file: str,
        line: int,
        passed_observed: int = 0,
        passed_not_observed: int = 0,
        failed_observed: int = 0,
        failed_not_observed: int = 0,
    ):
        super().__init__()
        self.file = file
        self.line = line
        self.passed = passed_observed + passed_not_observed
        self.passed_observed = passed_observed
        self.passed_not_observed = passed_not_observed
        self.failed = failed_observed + failed_not_observed
        self.failed_observed = failed_observed
        self.failed_not_observed = failed_not_observed
        self.last_evaluation: dict[EventFile, dict[int, EvaluationResult]] = dict()
        self.weights: Dict[int, float] = dict()
        self.weight: float = 1

    def __hash__(self):
        return hash((self.file, self.line, self.analysis_type()))

    def __eq__(self, other):
        if not isinstance(other, Spectrum):
            return False
        return (
            self.file == other.file
            and self.line == other.line
            and self.analysis_type() == other.analysis_type()
        )

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}"

    def serialize(self):
        return {
            "file": self.file,
            "line": self.line,
            "passed": self.passed,
            "passed_observed": self.passed_observed,
            "passed_not_observed": self.passed_not_observed,
            "failed": self.failed,
            "failed_observed": self.failed_observed,
            "failed_not_observed": self.failed_not_observed,
            "type": self.analysis_type().value,
            "weight": self.weight,
        }

    def _deserialize(self, s: dict):
        self.passed = s["passed"]
        self.passed_observed = s["passed_observed"]
        self.passed_not_observed = s["passed_not_observed"]
        self.failed = s["failed"]
        self.failed_observed = s["failed_observed"]
        self.failed_not_observed = s["failed_not_observed"]
        self.weight = s["weight"] if "weight" in s else 1

    @staticmethod
    def default_evaluation() -> EvaluationResult:
        return EvaluationResult.FALSE

    def get_last_evaluation(
        self, id_: EventFile, thread_id: Optional[int] = None
    ) -> EvaluationResult:
        if id_ in self.last_evaluation and thread_id in self.last_evaluation[id_]:
            return self.last_evaluation[id_][thread_id]
        return self.default_evaluation()

    def get_metric(self, metric: Callable = None, use_weight: bool = False):
        if metric is None:
            metric = Spectrum.Ochiai
        try:
            m = metric(self)
            if numpy.isnan(m):
                m = 0
            if use_weight:
                m *= self.weight
            return m
        except ZeroDivisionError:
            return 0

    def get_suggestion(
        self, metric: Callable = None, base_dir: str = "", use_weight: bool = False
    ):
        self.assign_suspiciousness(metric, use_weight=use_weight)
        return Suggestion([Location(self.file, self.line)], self.suspiciousness)

    def assign_suspiciousness(self, metric: Callable = None, use_weight: bool = False):
        self.suspiciousness = self.get_metric(metric, use_weight=use_weight)

    def hit(self, id_, event, scope: Scope = None):
        if id_ in self.hits:
            if event.thread_id in self.hits[id_]:
                self.hits[id_][event.thread_id] += 1
            else:
                self.hits[id_][event.thread_id] = 1
            self.last_evaluation[id_][event.thread_id] = EvaluationResult.TRUE
        else:
            self.hits[id_] = {event.thread_id: 1}
            self.last_evaluation[id_] = {event.thread_id: EvaluationResult.TRUE}

    def pass_observed(self):
        self.passed_observed += 1

    def fail_observed(self):
        self.failed_observed += 1

    def set_passed(self, passed: int):
        self.passed = passed
        self.passed_not_observed = passed - self.passed_observed

    def set_failed(self, failed: int):
        self.failed = failed
        self.failed_not_observed = failed - self.failed_observed

    def adjust_weight(self, event_file: EventFile, weight: float):
        if event_file not in self.weights:
            self.weights[event_file] = weight
        else:
            self.weights[event_file] = max(self.weights[event_file], weight)

    def set_weight(self):
        self.weight = (
            sum(self.weights.values()) / len(self.weights) if self.weights else 0
        )

    def _check_hits(self, event_file: EventFile):
        if event_file in self.hits:
            return sum(self.hits[event_file].values()) > 0
        return False

    def finalize(self, passed: list[EventFile], failed: list[EventFile]):
        for event_file in failed:
            if self._check_hits(event_file):
                self.fail_observed()
        for event_file in passed:
            if self._check_hits(event_file):
                self.pass_observed()
        self.set_passed(len(passed))
        self.set_failed(len(failed))
        self.set_weight()

    def AMPLE(self):
        return abs(
            self.failed_observed / self.failed - self.passed_observed / self.passed
        )

    def AMPLE2(self):
        return self.failed_observed / self.failed - self.passed_observed / self.passed

    def Anderberg(self):
        return self.failed_observed / (
            self.failed_observed + 2 * (self.failed_not_observed + self.passed_observed)
        )

    def ArithmeticMean(self):
        return (
            2 * self.failed_observed * self.passed_not_observed
            - 2 * self.failed_not_observed * self.passed_observed
        ) / (
            (self.failed_observed + self.passed_observed)
            * (self.failed_not_observed + self.passed_not_observed)
            * self.failed
            * self.passed
        )

    def Binary(self):
        return 0 if self.failed_observed < self.failed else 1

    def CBIInc(self):
        return self.failed_observed / (
            self.failed_observed + self.passed_observed
        ) - self.failed / (self.failed + self.passed)

    def Cohen(self):
        return (
            2 * self.failed_observed * self.passed_not_observed
            - 2 * self.failed_not_observed * self.passed_observed
        ) / (
            (self.failed_observed + self.passed_observed) * self.passed
            + self.failed * (self.failed_not_observed + self.passed_not_observed)
        )

    def Crosstab(self):
        return (
            (
                self.failed_not_observed
                - (
                    (self.failed_observed + self.passed_observed)
                    * self.failed
                    / (self.failed + self.passed)
                )
            )
            ** 2
            / (
                (self.failed_observed + self.passed_observed)
                * self.failed
                / (self.failed + self.passed)
            )
            + (
                self.passed_observed
                - (
                    (self.failed_observed + self.passed_observed)
                    * self.passed
                    / (self.failed + self.passed)
                )
            )
            ** 2
            / (
                (self.failed_observed + self.passed_observed)
                * self.passed
                / (self.failed + self.passed)
            )
            + (
                self.failed_not_observed
                - (
                    (self.failed_not_observed + self.passed_not_observed)
                    * self.failed
                    / (self.failed + self.passed)
                )
            )
            ** 2
            / (
                (self.failed_not_observed + self.passed_not_observed)
                * self.failed
                / (self.failed + self.passed)
            )
            + (
                self.passed_not_observed
                - (
                    (self.failed_not_observed + self.passed_not_observed)
                    * self.passed
                    / (self.failed + self.passed)
                )
            )
            ** 2
            / (
                (self.failed_not_observed + self.passed_not_observed)
                * self.passed
                / (self.failed + self.passed)
            )
        )

    def Dice(self):
        return 2 * self.failed_observed / (self.failed + self.passed_observed)

    def DStar(self, n=2):
        return self.failed_observed**n / (
            self.failed_not_observed + self.passed_observed
        )

    def Euclid(self):
        return numpy.sqrt(self.failed_observed + self.passed_not_observed)

    def Fleiss(self):
        return (
            4 * self.failed_observed * self.passed_not_observed
            - 4 * self.failed_not_observed * self.passed_observed
            - (self.failed_not_observed - self.passed_observed) ** 2
        ) / (
            (2 * self.failed_observed + self.failed_not_observed + self.passed_observed)
            + (
                2 * self.passed_not_observed
                + self.failed_not_observed
                + self.passed_observed
            )
        )

    def GP02(self):
        return 2 * (
            self.failed_observed + numpy.sqrt(self.passed_not_observed)
        ) + numpy.sqrt(self.passed_observed)

    def GP03(self):
        return numpy.sqrt(
            abs(self.failed_observed**2 - numpy.sqrt(self.passed_observed))
        )

    def GP13(self):
        return self.failed_observed * (
            1 + 1 / (2 * self.passed_observed + self.failed_observed)
        )

    def GP19(self):
        return self.failed_observed * numpy.sqrt(
            abs(
                self.passed_observed
                - self.failed_observed
                + self.failed_not_observed
                - self.passed_not_observed
            )
        )

    def Goodman(self):
        return (
            2 * self.failed_observed - self.failed_not_observed - self.passed_observed
        ) / (2 * self.failed_observed + self.failed_not_observed + self.passed_observed)

    def Hamann(self):
        return (
            self.failed_observed
            + self.passed_not_observed
            - self.failed_not_observed
            - self.passed_observed
        ) / (self.failed + self.passed)

    def HammingEtc(self):
        return self.failed_observed + self.passed_not_observed

    def HarmonicMean(self):
        return (
            (
                self.failed_observed * self.passed_not_observed
                - self.failed_not_observed * self.passed_observed
            )
            * (
                (self.failed_observed + self.passed_observed)
                * (self.failed_not_observed + self.passed_not_observed)
                + self.failed * self.passed
            )
            / (
                (self.failed_observed + self.passed_observed)
                * (self.failed_not_observed + self.passed_not_observed)
                * self.failed
                * self.passed
            )
        )

    def Jaccard(self):
        return self.failed_observed / (self.failed + self.passed_observed)

    def Kulczynski1(self):
        return self.failed_observed / (self.failed_not_observed + self.passed_observed)

    def Kulczynski2(self):
        return (
            1
            / 2
            * (
                self.failed_observed / self.failed
                + self.failed_observed / (self.failed_observed + self.passed_observed)
            )
        )

    def M1(self):
        return (self.failed_observed + self.passed_not_observed) / (
            self.failed_not_observed + self.passed_observed
        )

    def M2(self):
        return self.failed_observed / (
            self.failed_observed
            + self.passed_not_observed
            + 2 * (self.failed_not_observed + self.passed_observed)
        )

    def Naish1(self):
        return -1 if self.failed_observed < self.failed else self.passed_not_observed

    def Naish2(self):
        return self.failed_observed - self.passed_observed / (self.passed + 1)

    def Ochiai(self):
        return self.failed_observed / numpy.sqrt(
            self.failed * (self.failed_observed + self.passed_observed)
        )

    def Ochiai2(self):
        return (
            self.failed_observed
            * self.passed_not_observed
            / numpy.sqrt(
                (self.failed_observed + self.passed_observed)
                * (self.failed_not_observed + self.passed_not_observed)
                * self.failed
                * self.passed
            )
        )

    def PairScoring(self):
        return self.failed_observed * (
            2 * self.passed_not_observed + self.passed_observed
        )

    def qe(self):
        return self.failed_observed / (self.failed_observed + self.passed_observed)

    def RogersAndTanimoto(self):
        return (self.failed_observed + self.passed_not_observed) / (
            self.failed_observed
            + self.passed_not_observed
            + 2 * (self.failed_not_observed + self.passed_observed)
        )

    def Rogot1(self):
        return (
            1
            / 2
            * (
                self.failed_observed
                / (
                    2 * self.failed_observed
                    + self.failed_not_observed
                    + self.passed_observed
                )
                + self.passed_not_observed
                / (
                    2 * self.passed_not_observed
                    + self.failed_not_observed
                    + self.passed_observed
                )
            )
        )

    def Rogot2(self):
        return (
            1
            / 4
            * (
                self.failed_observed / (self.failed_observed + self.passed_observed)
                + self.failed_observed / self.failed
                + self.passed_not_observed / self.passed
                + self.passed_not_observed
                / (self.failed_not_observed + self.passed_not_observed)
            )
        )

    def RusselAndRao(self):
        return self.failed_observed / (self.failed + self.passed)

    def Scott(self):
        return (
            4 * self.failed_observed * self.passed_not_observed
            - 4 * self.failed_not_observed * self.passed_observed
            - (self.failed_not_observed - self.passed_observed) ** 2
        ) / (
            (2 * self.failed_observed + self.failed_not_observed + self.passed_observed)
            * (
                2 * self.passed_not_observed
                + self.failed_not_observed
                + self.passed_observed
            )
        )

    def SimpleMatching(self):
        return (self.failed_observed + self.passed_not_observed) / (
            self.failed + self.passed
        )

    def Sokal(self):
        return (
            2
            * (self.failed_observed + self.passed_not_observed)
            / (
                2 * (self.failed_observed + self.passed_not_observed)
                + self.failed_not_observed
                + self.passed_observed
            )
        )

    def SorensenDice(self):
        return (
            2
            * self.failed_observed
            / (
                2 * self.failed_observed
                + self.failed_not_observed
                + self.passed_observed
            )
        )

    def Tarantula(self):
        return (
            self.failed_observed
            / self.failed
            / (self.failed_observed / self.failed + self.passed_observed / self.passed)
        )

    def Wong1(self):
        return self.failed_observed

    def Wong2(self):
        return self.failed_observed - self.passed_observed

    def Wong3(self):
        return self.failed_observed - (
            self.passed_observed
            if self.passed_observed <= 2
            else (
                2 + 0.1 * (self.passed_observed - 2)
                if self.passed_observed <= 10
                else 2.8 + 0.001 * (self.passed_observed - 10)
            )
        )

    def Zoltar(self):
        return self.failed_observed / (
            self.failed
            + self.passed_observed
            + 10000
            * self.failed_not_observed
            * self.passed_observed
            / self.failed_observed
        )


class DummySpectrum(Spectrum):
    @staticmethod
    def deserialize(s: dict):
        return DummySpectrum("", 0)

    @staticmethod
    def analysis_type():
        pass

    @staticmethod
    def events():
        return []


class Line(Spectrum):
    def __init__(self, event: LineEvent | MetaEvent):
        super().__init__(event.file, event.line)

    @staticmethod
    def deserialize(s: dict):
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
            ]
        )
        assert s["type"] == AnalysisType.LINE.value
        analysis_object = Line(MetaEvent(s["file"], s["line"]))
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.LINE

    @staticmethod
    def events():
        return [EventType.LINE]


class Function(Spectrum):
    def __init__(self, event: FunctionEnterEvent | MetaEvent):
        super().__init__(event.file, event.line)
        self.function = event.function

    def __hash__(self):
        return hash((self.file, self.line, self.function, self.analysis_type()))

    def __eq__(self, other):
        return (
            isinstance(other, Function)
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
    def deserialize(s: dict):
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
                "function",
            ]
        )
        assert s["type"] == AnalysisType.FUNCTION.value
        analysis_object = Function(
            MetaEvent(s["file"], s["line"], function=s["function"])
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.FUNCTION

    @staticmethod
    def events():
        return [EventType.FUNCTION_ENTER]

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


class DefUse(Spectrum):
    def __init__(
        self, def_event: DefEvent | MetaEvent, use_event: UseEvent | MetaEvent
    ):
        super().__init__(def_event.file, def_event.line)
        self.use_file = use_event.file
        self.use_line = use_event.line
        self.var = def_event.var

    def __hash__(self):
        return hash(
            (
                self.file,
                self.line,
                self.use_file,
                self.use_line,
                self.var,
                self.analysis_type(),
            )
        )

    def __eq__(self, other):
        return (
            isinstance(other, DefUse)
            and self.file == other.file
            and self.line == other.line
            and self.use_file == other.use_file
            and self.use_line == other.use_line
            and self.var == other.var
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["use_file"] = self.use_file
        default["use_line"] = self.use_line
        default["var"] = self.var
        return default

    @staticmethod
    def deserialize(s: dict):
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
                "use_file",
                "use_line",
                "var",
            ]
        )
        assert s["type"] == AnalysisType.DEF_USE.value
        analysis_object = DefUse(
            MetaEvent(s["file"], s["line"], var=s["var"]),
            MetaEvent(s["use_file"], s["use_line"]),
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def analysis_type():
        return AnalysisType.DEF_USE

    @staticmethod
    def events():
        return [
            EventType.DEF,
            EventType.USE,
            EventType.FUNCTION_ENTER,
            EventType.FUNCTION_EXIT,
            EventType.FUNCTION_ERROR,
        ]

    def get_suggestion(
        self, metric: Callable = None, base_dir: str = "", use_weight: bool = False
    ):
        return Suggestion(
            [Location(self.file, self.line), Location(self.use_file, self.use_line)],
            self.get_metric(metric, use_weight=use_weight),
        )

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.use_file}:{self.use_line}:{self.var}"


class ModifiableSpectrum(Spectrum, ABC):
    pass


class Loop(ModifiableSpectrum):
    def __init__(
        self,
        event: LoopBeginEvent | LoopHitEvent | LoopEndEvent | MetaEvent,
        evaluate_hit: Optional[Callable] = None,
    ):
        super().__init__(event.file, event.line)
        self.loop_stack = dict()
        self.evaluate_hit = evaluate_hit if evaluate_hit else self.evaluate_hit_0

    def __hash__(self):
        return hash(
            (self.file, self.line, self.evaluate_hit.__name__, self.analysis_type())
        )

    def __eq__(self, other):
        return (
            isinstance(other, Loop)
            and self.file == other.file
            and self.line == other.line
            and self.evaluate_hit == other.evaluate_hit
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["evaluate_hit"] = self.evaluate_hit.__name__
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
                "evaluate_hit",
            ]
        )
        assert s["type"] == AnalysisType.LOOP.value
        analysis_object = Loop(
            MetaEvent(s["file"], s["line"]), getattr(Loop, s["evaluate_hit"])
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def evaluate_hit_0(x):
        return x == 0

    @staticmethod
    def evaluate_hit_1(x):
        return x == 1

    @staticmethod
    def evaluate_hit_more(x):
        return x > 1

    @staticmethod
    def analysis_type():
        return AnalysisType.LOOP

    @staticmethod
    def events():
        return [EventType.LOOP_BEGIN, EventType.LOOP_HIT, EventType.LOOP_END]

    def start_loop(self, thread_id: Optional[int] = None):
        self.loop_stack.setdefault(thread_id, []).append(0)

    def hit_loop(self, thread_id: Optional[int] = None):
        if thread_id in self.loop_stack:
            if self.loop_stack[thread_id]:
                self.loop_stack[thread_id][-1] += 1
            else:
                self.loop_stack[thread_id].append(1)
        else:
            self.loop_stack[thread_id] = [1]

    def hit(self, id_, event, scope: Scope = None):
        if (
            self.loop_stack
            and event.thread_id in self.loop_stack
            and self.loop_stack[event.thread_id]
        ):
            hits = self.loop_stack[event.thread_id].pop()
        else:
            hits = 0
        result = (
            EvaluationResult.TRUE if self.evaluate_hit(hits) else EvaluationResult.FALSE
        )
        if id_ in self.hits:
            if event.thread_id in self.hits[id_]:
                self.hits[id_][event.thread_id].append(hits)
            else:
                self.hits[id_][event.thread_id] = [hits]
            self.last_evaluation[id_][event.thread_id] = result
        else:
            self.hits[id_] = {event.thread_id: [hits]}
            self.last_evaluation[id_] = {event.thread_id: result}

    def _check_hits(self, event_file: EventFile):
        if event_file in self.hits:
            for thread_hits in self.hits[event_file].values():
                if any(map(self.evaluate_hit, thread_hits)):
                    return True
        return False

    def get_suggestion(
        self, metric: Callable = None, base_dir: str = "", use_weight: bool = False
    ):
        finder = self.loop_finder(self.file, self.line)
        return Suggestion(
            [Location(self.file, line) for line in finder.get_locations(base_dir)],
            self.get_metric(metric, use_weight=use_weight),
        )

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}"


class Length(ModifiableSpectrum):
    def __init__(
        self,
        event: LenEvent,
        evaluate_hit: Optional[Callable] = None,
    ):
        super().__init__(event.file, event.line)
        self.var = event.var
        self.evaluate_length = evaluate_hit if evaluate_hit else self.evaluate_length_0

    def __hash__(self):
        return hash(
            (
                self.file,
                self.line,
                self.var,
                self.evaluate_length.__name__,
                self.analysis_type(),
            )
        )

    def __eq__(self, other):
        return (
            isinstance(other, Length)
            and self.file == other.file
            and self.line == other.line
            and self.var == other.var
            and self.evaluate_length == other.evaluate_length
            and self.analysis_type() == other.analysis_type()
        )

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        default["evaluate_length"] = self.evaluate_length.__name__
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
                "var",
                "evaluate_length",
            ]
        )
        assert s["type"] == AnalysisType.LENGTH.value
        analysis_object = Length(
            MetaEvent(s["file"], s["line"], var=s["var"]),
            getattr(Length, s["evaluate_length"]),
        )
        analysis_object._deserialize(s)
        return analysis_object

    @staticmethod
    def evaluate_length_0(x):
        return x == 0

    @staticmethod
    def evaluate_length_1(x):
        return x == 1

    @staticmethod
    def evaluate_length_more(x):
        return x > 1

    @staticmethod
    def analysis_type():
        return AnalysisType.LENGTH

    @staticmethod
    def events():
        return [EventType.LEN]

    def hit(self, id_, event, scope: Scope = None):
        result = (
            EvaluationResult.TRUE
            if self.evaluate_length(event.length)
            else EvaluationResult.FALSE
        )
        if id_ in self.hits:
            if event.thread_id in self.hits[id_]:
                self.hits[id_][event.thread_id].append(event.length)
            else:
                self.hits[id_][event.thread_id] = [event.length]
            self.last_evaluation[id_][event.thread_id] = result
        else:
            self.hits[id_] = {event.thread_id: [event.length]}
            self.last_evaluation[id_] = {event.thread_id: result}

    def _check_hits(self, event_file: EventFile):
        if event_file in self.hits:
            for thread_lengths in self.hits[event_file].values():
                if any(map(self.evaluate_length, thread_lengths)):
                    return True
        return False

    def __str__(self):
        return f"{self.analysis_type()}:{self.file}:{self.line}:{self.var}:{self.evaluate_length.__name__}"
