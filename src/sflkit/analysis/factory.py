import abc
from threading import Lock
from typing import List, Type, Set

from sflkitlib.events import EventType
from sflkitlib.events.event import DefEvent

from sflkit.analysis.analysis_type import AnalysisObject, AnalysisType
from sflkit.analysis.predicate import (
    Branch,
    Condition,
    Comp,
    ScalarPair,
    VariablePredicate,
    ReturnPredicate,
    NonePredicate,
    EmptyStringPredicate,
    IsAsciiPredicate,
    ContainsDigitPredicate,
    ContainsSpecialPredicate,
    EmptyBytesPredicate,
    FunctionErrorPredicate,
)
from sflkit.analysis.spectra import Line, Function, Loop, DefUse, Length
from sflkit.events.event_file import EventFile
from sflkit.model.scope import Scope


class AnalysisFactory(abc.ABC):
    def __init__(self):
        self.objects = dict()
        self._lock = Lock()

    @abc.abstractmethod
    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        raise NotImplementedError()

    def handle(self, event, event_file: EventFile, scope: Scope = None):
        analysis = self.get_analysis(event, event_file, scope=scope)
        if analysis:
            return analysis
        else:
            return self.default()

    def reset(self, event_file: EventFile):
        pass

    @staticmethod
    def default():
        return list()

    def get_all(self) -> Set[AnalysisObject]:
        return set(self.objects.values())


class CombinationFactory(AnalysisFactory):
    def __init__(self, factories: List[AnalysisFactory]):
        super().__init__()
        self.factories = factories

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        return sum(
            [factory.handle(event, event_file, scope) for factory in self.factories],
            start=list(),
        )

    def reset(self, event_file: EventFile):
        [f.reset(event_file) for f in self.factories]

    def get_all(self) -> Set[AnalysisObject]:
        return set().union(*map(lambda f: f.get_all(), self.factories))


class LineFactory(AnalysisFactory):
    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.LINE:
            key = (Line.analysis_type(), event.file, event.line)
            with self._lock:
                if key not in self.objects:
                    self.objects[key] = Line(event)
            return [self.objects[key]]
        return []


class BranchFactory(AnalysisFactory):
    def __init__(self, else_: bool = True):
        super().__init__()
        self.else_ = else_

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.BRANCH:
            key = (Branch.analysis_type(), event.file, event.line, event.then_id)
            then = event.then_id < event.else_id
            with self._lock:
                if key not in self.objects:
                    self.objects[key] = Branch(event, then=then, then_id=event.then_id)
            if self.else_ and event.else_id >= 0:
                else_key = (
                    Branch.analysis_type(),
                    event.file,
                    event.line,
                    event.else_id,
                )
                with self._lock:
                    if else_key not in self.objects:
                        self.objects[else_key] = Branch(
                            event, then=not then, then_id=event.else_id
                        )
                return [self.objects[key], self.objects[else_key]]
            return [self.objects[key]]

        return []


class FunctionFactory(AnalysisFactory):
    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.FUNCTION_ENTER:
            key = (Function.analysis_type(), event.file, event.line, event.function_id)
            with self._lock:
                if key not in self.objects:
                    self.objects[key] = Function(event)
            return [self.objects[key]]
        return []


class LoopFactory(AnalysisFactory):
    def __init__(self, hit_0: bool = True, hit_1: bool = True, hit_more: bool = True):
        super().__init__()
        self.hit_0 = hit_0
        self.hit_1 = hit_1
        self.hit_more = hit_more

    def get_all(self) -> Set[AnalysisObject]:
        return set(obj for value in self.objects.values() for obj in value)

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type in (
            EventType.LOOP_BEGIN,
            EventType.LOOP_HIT,
            EventType.LOOP_END,
        ):
            key = (Loop.analysis_type(), event.file, event.line, event.loop_id)
            with self._lock:
                if key not in self.objects:
                    self.objects[key] = []
                    if self.hit_0:
                        self.objects[key].append(Loop(event, Loop.evaluate_hit_0)),
                    if self.hit_1:
                        self.objects[key].append(Loop(event, Loop.evaluate_hit_1)),
                    if self.hit_more:
                        self.objects[key].append(Loop(event, Loop.evaluate_hit_more)),
            if event.event_type == EventType.LOOP_BEGIN:
                for obj in self.objects[key]:
                    obj.start_loop(thread_id=event.thread_id)
            elif event.event_type == EventType.LOOP_HIT:
                for obj in self.objects[key]:
                    obj.hit_loop(thread_id=event.thread_id)
            elif event.event_type == EventType.LOOP_END:
                return self.objects[key][:]
            return list()
        return []


class DefUseFactory(AnalysisFactory):
    class DefScope:
        def __init__(self, parent: "DefUseFactory.DefScope" = None):
            self.parent: "DefUseFactory.DefScope" = parent
            self.def_events: dict[tuple[str, int], DefEvent] = dict()

        def enter(self):
            return DefUseFactory.DefScope(self)

        def exit(self):
            return self.parent or self

        def add(self, var_name: str, var_id: int, def_event: DefEvent):
            self.def_events[(var_name, var_id)] = def_event

        def event(self, var_name: str, var_id: int) -> DefEvent:
            current = self
            while current is not None:
                if (var_name, var_id) in current.def_events:
                    return current.def_events[(var_name, var_id)]
                current = current.parent
            return None

    def __init__(self):
        super().__init__()
        self.id_to_def: dict[EventFile, dict[tuple[str, int], DefEvent]] = dict()
        self.id_to_def_thread: dict[
            EventFile, dict[int, dict[tuple[str, int], DefEvent]]
        ] = dict()
        self.def_stack: dict[EventFile, dict[int, DefUseFactory.DefScope]] = dict()

    def reset(self, event_file: EventFile):
        if event_file in self.id_to_def:
            del self.id_to_def[event_file]
        if event_file in self.id_to_def_thread:
            del self.id_to_def_thread[event_file]
        if event_file in self.def_stack:
            del self.def_stack[event_file]

    def _find_def_event(
        self,
        event_file: EventFile,
        thread_id: int,
        var_name: str,
        var_id: int,
    ) -> DefEvent:
        # Strategy 1: Check in scope stack (from innermost to outermost)
        def_event = None
        if event_file in self.def_stack and thread_id in self.def_stack[event_file]:
            def_event = self.def_stack[event_file][thread_id].event(var_name, var_id)

        # Strategy 2: Look up in the thread-specific DEF stack
        if def_event is None:
            if (
                event_file in self.id_to_def_thread
                and thread_id in self.id_to_def_thread[event_file]
            ):
                def_event = self.id_to_def_thread[event_file][thread_id].get(
                    (var_name, var_id), None
                )

        # Strategy 3: Look up in the global DEF stack (other threads)
        if def_event is None:
            if event_file in self.id_to_def:
                def_event = self.id_to_def[event_file].get((var_name, var_id), None)

        return def_event

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        thread_id = event.thread_id

        if event.event_type == EventType.DEF:
            key = (event.var, event.var_id)

            # Initialize structures if needed
            if event_file not in self.id_to_def:
                self.id_to_def[event_file] = dict()
            if event_file not in self.id_to_def_thread:
                self.id_to_def_thread[event_file] = dict()
            if thread_id not in self.id_to_def_thread[event_file]:
                self.id_to_def_thread[event_file][thread_id] = dict()
            if event_file not in self.def_stack:
                self.def_stack[event_file] = dict()
            if thread_id not in self.def_stack[event_file]:
                self.def_stack[event_file][thread_id] = DefUseFactory.DefScope()

            # Store the DEF event
            self.id_to_def[event_file][key] = event
            self.id_to_def_thread[event_file][thread_id][key] = event
            self.def_stack[event_file][thread_id].add(event.var, event.var_id, event)

        elif event.event_type == EventType.USE:
            def_event = self._find_def_event(
                event_file, thread_id, event.var, event.var_id
            )

            if def_event:
                key = (
                    DefUse.analysis_type(),
                    def_event.file,
                    def_event.line,
                    event.file,
                    event.line,
                    event.var,
                )
                with self._lock:
                    if key not in self.objects:
                        self.objects[key] = DefUse(def_event, event)
                return [self.objects[key]]
        elif event.event_type == EventType.FUNCTION_ENTER:
            if event_file not in self.def_stack:
                self.def_stack[event_file] = dict()
            if thread_id not in self.def_stack[event_file]:
                self.def_stack[event_file][thread_id] = DefUseFactory.DefScope()
            else:
                self.def_stack[event_file][thread_id] = self.def_stack[event_file][
                    thread_id
                ].enter()
        elif (
            event.event_type == EventType.FUNCTION_EXIT
            or event.event_type == EventType.FUNCTION_ERROR
        ):
            if event_file in self.def_stack and thread_id in self.def_stack[event_file]:
                self.def_stack[event_file][thread_id] = self.def_stack[event_file][
                    thread_id
                ].exit()
        return []


class ConditionFactory(AnalysisFactory):
    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        objects = list()
        if event.event_type == EventType.CONDITION:
            for negate in (True, False):
                key = (
                    Condition.analysis_type(),
                    event.file,
                    event.line,
                    event.condition,
                    negate,
                )
                with self._lock:
                    if key not in self.objects:
                        self.objects[key] = Condition(
                            event.file, event.line, event.condition, negate=negate
                        )
                objects.append(self.objects[key])
        return objects


class ComparisonFactory(AnalysisFactory, abc.ABC):
    def __init__(
        self,
        eq: bool = True,
        ne: bool = True,
        lt: bool = True,
        le: bool = True,
        gt: bool = True,
        ge: bool = True,
    ):
        super().__init__()
        self.comparators = []
        if eq:
            self.comparators.append(Comp.EQ)
        if ne:
            self.comparators.append(Comp.NE)
        if lt:
            self.comparators.append(Comp.LT)
        if le:
            self.comparators.append(Comp.LE)
        if gt:
            self.comparators.append(Comp.GT)
        if ge:
            self.comparators.append(Comp.GE)


class ScalarPairFactory(ComparisonFactory):
    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.DEF:
            variables = scope.get_all_vars()
            objects = list()
            if event.type_ in ["int", "float", "bool", "str", "bytes"]:
                for types in (["int", "float", "bool"], ["str"], ["bytes"]):
                    if event.type_ in types:
                        for variable in variables:
                            if variable.type_ in types:
                                for comp in self.comparators:
                                    key = (
                                        ScalarPair.analysis_type(),
                                        event.file,
                                        event.line,
                                        event.var,
                                        variable.var,
                                        comp,
                                        types[0],
                                    )
                                    with self._lock:
                                        if key not in self.objects:
                                            self.objects[key] = ScalarPair(
                                                event, comp, variable.var
                                            )
                                    objects.append(self.objects[key])
            else:
                for variable in variables:
                    if variable.type_ == event.type_:
                        for comp in (Comp.EQ, Comp.NE):
                            if comp in self.comparators:
                                key = (
                                    ScalarPair.analysis_type(),
                                    event.file,
                                    event.line,
                                    event.var,
                                    variable.var,
                                    comp,
                                    event.type_,
                                )
                                with self._lock:
                                    if key not in self.objects:
                                        self.objects[key] = ScalarPair(
                                            event, comp, variable.var
                                        )
                                objects.append(self.objects[key])
            return objects
        return []


class VariableFactory(ComparisonFactory):
    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.DEF and event.type_ in [
            "int",
            "float",
            "bool",
        ]:
            objects = list()
            for comp in self.comparators:
                key = (
                    VariablePredicate.analysis_type(),
                    event.file,
                    event.line,
                    event.var,
                    comp,
                    "int",
                )
                with self._lock:
                    if key not in self.objects:
                        self.objects[key] = VariablePredicate(event, comp)
                objects.append(self.objects[key])
            return objects
        return []


class ReturnFactory(ComparisonFactory):
    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.FUNCTION_EXIT:
            objects = list()
            if event.type_ in ("int", "float", "bool", "str", "bytes"):
                if event.type_ in ("int", "float", "bool"):
                    type_, tr = "num", 0
                    compare = Comp
                elif event.type_ == "str":
                    type_, tr = "str", ""
                    compare = Comp.EQ, Comp.NE
                else:
                    type_, tr = "bytes", b""
                    compare = Comp.EQ, Comp.NE
                for comp in compare:
                    if comp in self.comparators:
                        key = (
                            ReturnPredicate.analysis_type(),
                            event.file,
                            event.line,
                            event.function,
                            comp,
                            type_,
                        )
                        with self._lock:
                            if key not in self.objects:
                                self.objects[key] = ReturnPredicate(
                                    event, comp, value=tr
                                )
                            objects.append(self.objects[key])
            elif event.type_ == "NoneType":
                for comp in Comp.EQ, Comp.NE:
                    if comp in self.comparators:
                        key = (
                            ReturnPredicate.analysis_type(),
                            event.file,
                            event.line,
                            event.function,
                            comp,
                            event.type_,
                        )
                        with self._lock:
                            if key not in self.objects:
                                self.objects[key] = ReturnPredicate(
                                    event, comp, value=None
                                )
                        objects.append(self.objects[key])
            else:
                for comp in Comp.EQ, Comp.NE:
                    if comp in self.comparators:
                        key = (
                            ReturnPredicate.analysis_type(),
                            event.file,
                            event.line,
                            event.function,
                            comp,
                            "NoneType",
                        )
                        with self._lock:
                            if key not in self.objects:
                                self.objects[key] = ReturnPredicate(
                                    event, comp, value=None
                                )
                        objects.append(self.objects[key])
            return objects
        return []


class ConstantCompFactory(AnalysisFactory):
    def __init__(self, class_: Type[AnalysisObject]):
        super().__init__()
        self.class_ = class_

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.DEF:
            objects = list()
            for comp in Comp.EQ, Comp.NE:
                key = (
                    self.class_.analysis_type(),
                    event.file,
                    event.line,
                    event.var,
                    comp,
                )
                with self._lock:
                    if key not in self.objects:
                        # noinspection PyArgumentList
                        self.objects[key] = self.class_(event)
                objects.append(self.objects[key])
            return objects
        return []


class NoneFactory(ConstantCompFactory):
    def __init__(self):
        super().__init__(NonePredicate)


class EmptyStringFactory(ConstantCompFactory):
    def __init__(self):
        super().__init__(EmptyStringPredicate)


class EmptyBytesFactory(ConstantCompFactory):
    def __init__(self):
        super().__init__(EmptyBytesPredicate)


class PredicateFunctionFactory(AnalysisFactory):
    def __init__(self, class_: Type[AnalysisObject]):
        super().__init__()
        self.class_ = class_

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.DEF:
            key = (
                self.class_.analysis_type(),
                event.file,
                event.line,
                event.var,
            )
            with self._lock:
                if key not in self.objects:
                    # noinspection PyArgumentList
                    self.objects[key] = self.class_(event)
            return [self.objects[key]]
        return []


class IsAsciiFactory(PredicateFunctionFactory):
    def __init__(self):
        super().__init__(IsAsciiPredicate)


class ContainsDigitFactory(PredicateFunctionFactory):
    def __init__(self):
        super().__init__(ContainsDigitPredicate)


class ContainsSpecialFactory(PredicateFunctionFactory):
    def __init__(self):
        super().__init__(ContainsSpecialPredicate)


class LengthFactory(AnalysisFactory):
    def __init__(
        self, length_0: bool = True, length_1: bool = True, length_more: bool = True
    ):
        super().__init__()
        self.length_0 = length_0
        self.length_1 = length_1
        self.length_more = length_more

    def get_all(self) -> Set[AnalysisObject]:
        return set(obj for value in self.objects.values() for obj in value)

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.LEN:
            key = (Length.analysis_type(), event.file, event.line, event.var)
            with self._lock:
                if key not in self.objects:
                    self.objects[key] = []
                    if self.length_0:
                        self.objects[key].append(
                            Length(event, Length.evaluate_length_0)
                        ),
                    if self.length_1:
                        self.objects[key].append(
                            Length(event, Length.evaluate_length_1)
                        ),
                    if self.length_more:
                        self.objects[key].append(
                            Length(event, Length.evaluate_length_more)
                        )
            return self.objects[key][:]
        return []


class FunctionErrorFactory(AnalysisFactory):
    def __init__(self):
        super().__init__()
        self.function_mapping = dict()

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.FUNCTION_ENTER:
            self.function_mapping[event.function_id] = event.line
        if event.event_type in (EventType.FUNCTION_ERROR, EventType.FUNCTION_EXIT):
            line = self.function_mapping.get(event.function_id, event.line)
            key = (
                FunctionErrorPredicate.analysis_type(),
                event.file,
                line,
                event.function_id,
            )
            with self._lock:
                if key not in self.objects:
                    self.objects[key] = FunctionErrorPredicate(
                        event.file, line, event.function
                    )
            return [self.objects[key]]
        return []


analysis_factory_mapping = {
    AnalysisType.LINE: LineFactory,
    AnalysisType.BRANCH: BranchFactory,
    AnalysisType.LOOP: LoopFactory,
    AnalysisType.LENGTH: LengthFactory,
    AnalysisType.CONDITION: ConditionFactory,
    AnalysisType.NONE: NoneFactory,
    AnalysisType.DEF_USE: DefUseFactory,
    AnalysisType.SPECIAL_STRING: ContainsSpecialFactory,
    AnalysisType.DIGIT_STRING: ContainsDigitFactory,
    AnalysisType.ASCII_STRING: IsAsciiFactory,
    AnalysisType.EMPTY_BYTES: EmptyBytesFactory,
    AnalysisType.EMPTY_STRING: EmptyStringFactory,
    AnalysisType.RETURN: ReturnFactory,
    AnalysisType.VARIABLE: VariableFactory,
    AnalysisType.SCALAR_PAIR: ScalarPairFactory,
    AnalysisType.FUNCTION: FunctionFactory,
    AnalysisType.FUNCTION_ERROR: FunctionErrorFactory,
}
