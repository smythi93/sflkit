import abc
from collections import OrderedDict
from threading import Lock
from typing import Dict, FrozenSet, List, Optional, Set, Type

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
    #: Event types this factory can produce analysis for. ``None`` means "any",
    #: which is the safe default for a factory that has not declared itself.
    #: :class:`CombinationFactory` uses this to skip factories that would only
    #: look at the event type and return nothing: with a dozen factories
    #: registered, all but one or two do exactly that for any given event.
    EVENT_TYPES: Optional[FrozenSet[EventType]] = None

    def __init__(self):
        self.objects = dict()
        self._lock = Lock()

    def __getstate__(self) -> dict:
        # Factories are shipped to worker processes to analyze a share of the
        # runs. A lock is not picklable and guards nothing across processes,
        # so it is dropped and remade on arrival.
        state = dict(self.__dict__)
        state.pop("_lock", None)
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
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

    def exit_scope(self, event_file: EventFile, scope_id: int):
        """
        Release whatever this factory kept for a scope that has just ended.

        :param event_file: The run.
        :param scope_id: Identity of the scope being left.

        Scope ids are handed out per function call, so a factory that keeps
        state per scope grows with the number of calls a run makes unless it
        is told when a scope dies.
        """

    @staticmethod
    def default():
        return list()

    def get_all(self) -> Set[AnalysisObject]:
        return set(self.objects.values())

    def adopt(self, objects) -> None:
        """
        Take ownership of analysis objects built elsewhere.

        Used after a process-parallel run, where the objects were built in
        worker processes and merged in the parent: the parent's own factories
        never saw an event, so the merged objects are installed here for the
        rest of the analyzer to read back.

        :param objects: The objects to own.
        """
        self.objects = dict(enumerate(objects))


class CombinationFactory(AnalysisFactory):
    def __init__(self, factories: List[AnalysisFactory]):
        super().__init__()
        self.factories = factories
        self._dispatch: Dict[EventType, List[AnalysisFactory]] = {
            event_type: [
                factory
                for factory in factories
                if factory.EVENT_TYPES is None or event_type in factory.EVENT_TYPES
            ]
            for event_type in EventType
        }

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        analysis = list()
        for factory in self._dispatch.get(event.event_type, self.factories):
            analysis.extend(factory.handle(event, event_file, scope))
        return analysis

    def reset(self, event_file: EventFile):
        [f.reset(event_file) for f in self.factories]

    def exit_scope(self, event_file: EventFile, scope_id: int):
        for factory in self.factories:
            factory.exit_scope(event_file, scope_id)

    def get_all(self) -> Set[AnalysisObject]:
        return set(self.objects.values()).union(
            *map(lambda f: f.get_all(), self.factories)
        )


class LineFactory(AnalysisFactory):
    EVENT_TYPES = frozenset({EventType.LINE})

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
    EVENT_TYPES = frozenset({EventType.BRANCH})

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
    EVENT_TYPES = frozenset({EventType.FUNCTION_ENTER})

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
    EVENT_TYPES = frozenset(
        {EventType.LOOP_BEGIN, EventType.LOOP_HIT, EventType.LOOP_END}
    )

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
    EVENT_TYPES = frozenset({EventType.DEF, EventType.USE})

    #: How many cross-thread definitions to remember per run. The scope chain
    #: answers every lookup within a thread, so this map only has to cover a
    #: use whose definition happened in *another* thread, and it is bounded
    #: because its key holds ``id(value)``: ids of dead objects would otherwise
    #: accumulate for the length of the run, and worse, CPython recycles them,
    #: so a stale entry can match an unrelated later object and invent a
    #: def-use pair that never existed.
    CROSS_THREAD_LIMIT = 4096

    def __init__(self):
        super().__init__()
        self.id_to_def: dict[EventFile, OrderedDict[tuple[str, int], DefEvent]] = dict()
        self.def_stack: dict[EventFile, dict[int, dict[tuple[str, int], DefEvent]]] = (
            dict()
        )

    def reset(self, event_file: EventFile):
        if event_file in self.id_to_def:
            del self.id_to_def[event_file]
        if event_file in self.def_stack:
            del self.def_stack[event_file]

    def exit_scope(self, event_file: EventFile, scope_id: int):
        """
        Drop the definitions made in a scope that has ended.

        Nothing can reach them any more: a use is resolved against the scope it
        happens in, and that scope is gone. Without this the stack kept one
        dict, and every ``DefEvent`` in it, for every function call the run
        ever made.

        :param event_file: The run.
        :param scope_id: Identity of the scope being left.
        """
        scopes = self.def_stack.get(event_file)
        if scopes is None:
            return
        definitions = scopes.pop(scope_id, None)
        if not definitions:
            return
        cross_thread = self.id_to_def.get(event_file)
        if cross_thread is None:
            return
        # A definition whose scope has ended has no business in the map that
        # reaches scopes off this chain: left behind it resolves a later use
        # against a scope that no longer exists, and since ids are recycled,
        # possibly against an entirely unrelated object.
        #
        # Attributes are the exception, and they are why this map exists at
        # all. `self.left = left` in a constructor is recorded as a definition
        # of `self.left`, but its lifetime is the object's, not the frame's:
        # every other method that reads it does so long after __init__ has
        # returned. Dropping those with the scope would lose exactly the
        # def-use pairs that span an object's methods. They stay, bounded by
        # CROSS_THREAD_LIMIT.
        #
        # Only entries this scope still owns are removed; a later definition of
        # the same name and id belongs to whichever scope overwrote it.
        for key, event in definitions.items():
            if "." in key[0]:
                continue
            if cross_thread.get(key) is event:
                del cross_thread[key]

    def _find_def_event(
        self,
        event_file: EventFile,
        scope: Optional[Scope],
        var_name: str,
        var_id: int,
    ) -> Optional[DefEvent]:
        """
        Find the definition a use refers to.

        :param event_file: The run.
        :param scope: The scope the use happens in.
        :param var_name: Name of the used variable.
        :param var_id: Identity of the value used.
        :returns: The defining event, or ``None``.

        Resolution walks the scope chain outwards, which is what the language
        itself does: a use sees its own scope first, then the scopes enclosing
        it. Consulting only the innermost scope missed every definition made by
        a caller, which is why a global map of every definition ever made was
        needed as a fallback. That map now only has to answer for definitions
        made in another thread, whose scopes are not on this chain.
        """
        key = (var_name, var_id)
        scopes = self.def_stack.get(event_file)
        if scopes:
            current = scope
            while current is not None:
                definitions = scopes.get(current.id)
                if definitions is not None:
                    def_event = definitions.get(key)
                    if def_event is not None:
                        return def_event
                current = current.parent
            if scope is None:
                definitions = scopes.get(0)
                if definitions is not None:
                    def_event = definitions.get(key)
                    if def_event is not None:
                        return def_event
        cross_thread = self.id_to_def.get(event_file)
        if cross_thread is not None:
            return cross_thread.get(key)
        return None

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        thread_id = event.thread_id
        scope_id = scope.id if scope else 0

        if event.event_type == EventType.DEF:
            key = (event.var, event.var_id)

            # Initialize structures if needed
            if event_file not in self.id_to_def:
                self.id_to_def[event_file] = OrderedDict()
            if event_file not in self.def_stack:
                self.def_stack[event_file] = dict()
            if scope_id not in self.def_stack[event_file]:
                self.def_stack[event_file][scope_id] = dict()

            # Store the DEF event
            cross_thread = self.id_to_def[event_file]
            cross_thread[key] = event
            cross_thread.move_to_end(key)
            while len(cross_thread) > self.CROSS_THREAD_LIMIT:
                cross_thread.popitem(last=False)
            self.def_stack[event_file][scope_id][key] = event

        elif event.event_type == EventType.USE:
            def_event = self._find_def_event(event_file, scope, event.var, event.var_id)

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
        return []


class ConditionFactory(AnalysisFactory):
    EVENT_TYPES = frozenset({EventType.CONDITION})

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
    EVENT_TYPES = frozenset({EventType.DEF})

    #: Whether a definition may be paired with module-level globals.
    #:
    #: Left on so existing callers keep the results they had. Turning it off
    #: pairs a definition only with the variables its function chain holds,
    #: which is both cheaper and sharper: at a definition in a library test,
    #: the overwhelming majority of variables in scope are the imported
    #: module's namespace, and a pair like ``line_no < __version_tuple__``
    #: relates a local to a constant that no execution of the program can
    #: change, so it separates no run from any other while still costing a
    #: predicate evaluation on every definition.
    PAIR_WITH_GLOBALS = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._analysis_cache: Dict[tuple, List[AnalysisObject]] = dict()

    def __getstate__(self) -> dict:
        # The cache is a pure memo of what _build_analysis would return, and
        # it can be large. Rebuilding it in the worker costs less than
        # shipping it there.
        state = super().__getstate__()
        state["_analysis_cache"] = dict()
        return state

    def _pair(self, key, event, comp, var) -> AnalysisObject:
        """
        Return the scalar pair for *key*, creating it on first use.

        The lock is only taken when the object is missing. Taking it on every
        lookup cost one acquire per pair per event, and these objects are
        created once and read forever after.

        :param key: Identity of the pair.
        :param event: The definition that triggered it.
        :param comp: The comparison.
        :param var: The variable compared against.
        :returns: The analysis object.
        """
        analysis = self.objects.get(key)
        if analysis is not None:
            return analysis
        with self._lock:
            analysis = self.objects.get(key)
            if analysis is None:
                analysis = ScalarPair(event, comp, var)
                self.objects[key] = analysis
            return analysis

    #: Pair lists already built, keyed by definition site and the scope
    #: bindings they were built against. See :meth:`get_analysis`.
    _CACHE_LIMIT = 200_000

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        """
        Return the scalar pairs for *event*, reusing an earlier list when the
        scope still binds the same names to the same types.

        The pairs a definition produces depend on the definition site and on
        which names of which types are in scope -- never on the values those
        names hold. So a definition inside a loop produces the very same list
        on every iteration, yet this used to rebuild it each time: walking a
        couple of hundred in-scope variables and, for each of the matching
        ones, allocating and hashing a seven-element key per comparison
        operator. That is the densest loop in tree building, and on a
        definition-heavy trace it is the majority of all analysis work.

        Keying on :meth:`Scope.type_signature` makes the check cost the
        nesting depth instead. The cache is dropped wholesale when it grows
        past ``_CACHE_LIMIT`` -- scope identities are never reused, so entries
        for scopes that have exited can never be hit again, and clearing is
        cheaper than tracking liveness per scope.

        :param event: The event, a definition or otherwise.
        :param event_file: The run it belongs to.
        :param scope: The variable scope at the definition.
        :returns: The pairs, or an empty list for a non-definition.
        """
        if event.event_type != EventType.DEF or scope is None:
            return self._build_analysis(event, event_file, scope=scope)
        key = (
            event.file,
            event.line,
            event.var,
            event.type_,
            scope.type_signature(include_root=self.PAIR_WITH_GLOBALS),
        )
        cached = self._analysis_cache.get(key)
        if cached is not None:
            return cached
        analysis = self._build_analysis(event, event_file, scope=scope)
        if len(self._analysis_cache) >= self._CACHE_LIMIT:
            self._analysis_cache.clear()
        self._analysis_cache[key] = analysis
        return analysis

    def _build_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        if event.event_type == EventType.DEF:
            variables = (
                scope.get_all_vars()
                if self.PAIR_WITH_GLOBALS
                else scope.get_local_vars()
            )
            objects = list()
            if event.type_ in ["int", "float", "bool", "str", "bytes"]:
                for types in (["int", "float", "bool"], ["str"], ["bytes"]):
                    if event.type_ in types:
                        # Ordered comparison is meaningful between numbers
                        # but not between two unrelated strings: `<` on str is
                        # lexicographic, so pairs like
                        # `unique < request_queue_size` assert nothing about the
                        # program while crowding out real causes. Equality still
                        # distinguishes states, so keep EQ/NE.
                        comparators = self.comparators
                        if types[0] in ("str", "bytes"):
                            comparators = [
                                c for c in comparators if c in (Comp.EQ, Comp.NE)
                            ]
                        # Hoisted out of the loop: this body runs for every
                        # pair of a definition and a variable in scope, which
                        # is the densest inner loop in the analysis.
                        analysis_type = ScalarPair.analysis_type()
                        file = event.file
                        line = event.line
                        var = event.var
                        type_ = types[0]
                        for variable in variables:
                            if variable.type_ in types:
                                for comp in comparators:
                                    key = (
                                        analysis_type,
                                        file,
                                        line,
                                        var,
                                        variable.var,
                                        comp.value,
                                        type_,
                                    )
                                    objects.append(
                                        self._pair(key, event, comp, variable.var)
                                    )
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
    EVENT_TYPES = frozenset({EventType.DEF})

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
    EVENT_TYPES = frozenset({EventType.FUNCTION_EXIT})

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
    EVENT_TYPES = frozenset({EventType.DEF})

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
    EVENT_TYPES = frozenset({EventType.DEF})

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
    EVENT_TYPES = frozenset({EventType.LEN})

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
    EVENT_TYPES = frozenset(
        {EventType.FUNCTION_ENTER, EventType.FUNCTION_ERROR, EventType.FUNCTION_EXIT}
    )

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
