"""
Runtime tracers that produce sflkit events without writing a trace.

Source instrumentation rewrites the program so that probe calls emit events.
A tracer instead leaves the program untouched and reconstructs the same events
from CPython's own monitoring hooks plus the static event mapping that
instrumentation already produces.

That trade buys three things. The run needs no instrumented copy of the
subject, so what executes is the program as shipped. Values are read from the
frame, so scoping is the interpreter's own rather than a scope reconstructed
from the event stream. And events go straight to listeners, so a run costs no
trace file at all.

Two backends materialize events identically:

* :class:`MonitoringTracer` uses :mod:`sys.monitoring` (PEP 669, Python 3.12+).
  It is the fast path: event types are opted into individually, and a location
  with nothing mapped to it is permanently disabled after its first hit, so the
  interpreter stops calling back for it. It observes every thread.
* :class:`SysTraceTracer` uses :func:`sys.settrace` and works on every version
  sflkit supports, at the cost of a Python callback per executed line. It is
  installed for threads started while tracing via :func:`threading.settrace`.

:func:`get_tracer` picks the best available backend.

Known limit, both backends: ``CONDITION`` and ``CONDITION_VALUE`` carry the
runtime truth value of a source expression. Recovering that from outside the
program would mean re-evaluating the expression in the frame, which can run
subject code a second time -- exactly the perturbation a probe must never
cause. The tracer therefore does not emit them; instrument the subject when
those types are required. Everything else is materialized in full.
"""

import abc
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sflkitlib.events import EventType
from sflkitlib.events.event import Event

from sflkit.events.mapping import EventMapping
from sflkit.logger import LOGGER
from sflkit.online.listener import EventListener
from sflkit.online.structure import BranchSite, SourceStructure, TrySite

#: Types whose value is recorded verbatim; anything else is recorded by type
#: name only. Mirrors ``sflkitlib.lib.add_def_event`` so that an online event
#: and its instrumented counterpart carry identical payloads.
_SCALAR_TYPES = (int, float, complex, str, bytes, bytearray, bool)

#: Function-boundary types, indexed per function rather than per line.
_FUNCTION_TYPES = frozenset(
    {EventType.FUNCTION_ENTER, EventType.FUNCTION_EXIT, EventType.FUNCTION_ERROR}
)

#: Event types the tracer can materialize. CONDITION/CONDITION_VALUE are absent
#: by design; see the module docstring.
SUPPORTED_EVENT_TYPES = frozenset(
    {
        EventType.LINE,
        EventType.BRANCH,
        EventType.DEF,
        EventType.USE,
        EventType.LEN,
        EventType.LOOP_BEGIN,
        EventType.LOOP_HIT,
        EventType.LOOP_END,
    }
    | _FUNCTION_TYPES
)


def env_int(name: str, default: int) -> int:
    """
    Read an integer budget from the environment.

    :param name: Environment variable to read.
    :param default: Value to use when it is unset or unreadable.
    :returns: The budget.
    """
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def value_and_type(value: Any, max_value_bytes: int = 0) -> Tuple[Any, str]:
    """
    Split *value* into the payload and type name an event should carry.

    :param value: The runtime value.
    :param max_value_bytes: Longest ``str``/``bytes`` value to keep whole;
        ``0`` keeps everything. Mirrors ``EVENTS_MAX_VALUE_BYTES``.
    :returns: ``(payload, type_name)``. Scalars and ``None`` keep their value;
        anything else is recorded as ``None`` with a qualified type name, so a
        trace never retains a reference to an arbitrary object.

    Oversized strings are cut to their prefix, as ``sflkitlib.lib._cap_value``
    does, because a definition of a multi-megabyte buffer would otherwise carry
    that whole buffer. The type name is that of the original value: truncating
    what is recorded must not change what the value is reported to be.
    """
    type_ = type(value)
    if type_ in _SCALAR_TYPES or value is None:
        if max_value_bytes > 0:
            # Only str and bytes have a length worth capping; a number has no
            # prefix to keep, and asking for its length raises.
            if type_ is str and len(value) > max_value_bytes:
                value = value[:max_value_bytes]
            elif type_ in (bytes, bytearray) and len(value) > max_value_bytes:
                value = bytes(value[:max_value_bytes])
        return value, type_.__name__
    return None, f"{type_.__module__}.{type_.__name__}"


class ThreadIds:
    """
    Assigns compact, run-local ids to threads.

    :class:`~sflkit.model.parallel.ParallelModel` keys one variable scope per
    thread id, so ids only need to be distinct within a run. Compact counting
    ids reproduce what ``sflkitlib.lib`` writes into instrumented traces, which
    keeps online and offline events comparable.

    :ivar enabled: When ``False`` every lookup returns ``None``, which is how a
        single-threaded run is represented.
    """

    def __init__(self, enabled: bool = False):
        """
        :param enabled: Whether to hand out ids at all.
        """
        self.enabled = enabled
        self._ids: Dict[int, int] = dict()
        self._lock = threading.Lock()

    def get(self) -> Optional[int]:
        """
        :returns: The calling thread's compact id, or ``None`` when thread
            support is off.
        """
        if not self.enabled:
            return None
        key = threading.get_ident()
        try:
            return self._ids[key]
        except KeyError:
            with self._lock:
                if key not in self._ids:
                    self._ids[key] = len(self._ids)
                return self._ids[key]


class FunctionTemplates:
    """
    The function-boundary templates of one function.

    :ivar enter: Template for entering the function, if instrumented.
    :ivar exits: Exit templates keyed by the line they were injected at. A
        function has one per ``return`` plus, usually, a fall-through exit.
    :ivar last_exit: Fall-through exit, used when a return happens at a line
        that carries no exit template of its own.
    :ivar error: Template for leaving through an exception.
    :ivar parameters: Def templates for the function's parameters. They sit on
        the ``def`` line, which never executes inside the function's own frame,
        so they are emitted on entry instead -- the moment the parameters are
        bound.
    :ivar line: Line the enter template sits on, used to tell same-named
        functions in one file apart.
    """

    __slots__ = ("enter", "exits", "last_exit", "error", "parameters", "line")

    def __init__(self):
        self.enter: Optional[Event] = None
        self.exits: Dict[int, Event] = dict()
        self.last_exit: Optional[Event] = None
        self.error: Optional[Event] = None
        self.parameters: List[Event] = list()
        self.line: int = 0


class Location:
    """
    Everything mapped to one ``(file, line)``, pre-sorted by how it is emitted.

    Splitting this once at setup keeps the hot path free of type tests: the
    line hook emits :attr:`templates`, and only touches the branch fields when
    they are actually populated.

    :ivar templates: Templates emitted as soon as the line runs. For a loop
        head these are the probes hoisted in front of the loop, so they are
        emitted on arrival only, not once per iteration.
    :ivar on_body: Templates due once the body is known to have been entered:
        the taken branch, and for a loop its hit and the binding of its target.
    :ivar on_exit: Templates due when the body was not entered: the other
        branch. For a loop this is its ``else``, which a ``break`` skips.
    :ivar on_finally: Templates due whenever a loop is left, however it is
        left. Instrumentation puts the loop-end probe in a ``finally``, so a
        ``break`` or a ``return`` from inside the body still records it.
    :ivar key: The ``(file, line)`` this record is filed under.
    :ivar site: Source structure deciding between the two.
    :ivar completed: Branch template recording that a ``try`` body finished
        without raising, or ``None``.
    :ivar try_site: Source structure for that ``try``.
    """

    __slots__ = (
        "templates",
        "on_body",
        "on_exit",
        "on_finally",
        "site",
        "completed",
        "try_site",
        "key",
    )

    def __init__(self, key: Tuple[str, int] = ("", 0)):
        self.key = key
        self.templates: List[Event] = list()
        self.on_body: List[Event] = list()
        self.on_exit: List[Event] = list()
        self.on_finally: List[Event] = list()
        self.site: Optional[BranchSite] = None
        self.completed: Optional[Event] = None
        self.try_site: Optional[TrySite] = None


class LocationIndex:
    """
    Turns an :class:`~sflkit.events.mapping.EventMapping` into runtime lookups.

    Instrumentation already decided which events exist and where; the tracer
    only recognizes the location and fills in the runtime values. The index
    also answers the question the fast backend asks constantly -- "is anything
    mapped here at all?" -- so uninteresting locations can be disabled for good.

    :ivar files: Mapping-relative paths of files carrying at least one event.
    :ivar skipped: Event types in the mapping the tracer cannot materialize.
    """

    def __init__(self, mapping: EventMapping, root: os.PathLike | str):
        """
        :param mapping: The mapping produced by instrumentation.
        :param root: Directory the mapping's file names are relative to, used
            to translate a frame's ``co_filename`` back into the mapping's name.
        """
        self.root = Path(root).resolve()
        self.files: Set[str] = set()
        self.skipped: Set[EventType] = set()
        self._by_location: Dict[Tuple[str, int], Location] = dict()
        self.structure = SourceStructure()
        self._functions: Dict[Tuple[str, str], List[FunctionTemplates]] = dict()
        self._resolved: Dict[str, Optional[str]] = dict()
        for event in sorted(mapping.mapping.values(), key=lambda e: e.event_id):
            if event.event_type not in SUPPORTED_EVENT_TYPES:
                self.skipped.add(event.event_type)
                continue
            self.files.add(event.file)
            if event.event_type in _FUNCTION_TYPES:
                self._add_function_template(event)
            else:
                self._location(event.file, event.line).templates.append(event)
        for templates in self._functions.values():
            templates.sort(key=lambda t: t.line)
        for name in self.files:
            self.structure.add_file(name, self.root / name)
        self._claim_parameters()
        self._claim_branches()
        if self.skipped:
            LOGGER.info(
                "Tracer cannot materialize %s; instrument the subject to collect them",
                ", ".join(sorted(type_.name for type_ in self.skipped)),
            )

    def _claim_parameters(self) -> None:
        """
        Move the def templates on each ``def`` line into their function.

        A parameter's def probe is placed on the line of the ``def`` itself,
        but that line only ever executes in the *enclosing* frame, when the
        function object is created. Left in the line index the templates would
        be looked up in the wrong frame, where the parameter names are not
        bound, and silently produce nothing.
        """
        for candidates in self._functions.values():
            for templates in candidates:
                if templates.enter is None:
                    continue
                key = (templates.enter.file, templates.enter.line)
                location = self._by_location.get(key)
                if location is None:
                    continue
                remaining = []
                for template in location.templates:
                    if template.event_type in (
                        EventType.DEF,
                        EventType.USE,
                        EventType.LEN,
                    ):
                        templates.parameters.append(template)
                    else:
                        remaining.append(template)
                location.templates = remaining
                templates.parameters.sort(key=lambda e: e.event_id)

    def _location(self, file: str, line: int) -> Location:
        """
        :param file: Mapping-relative file name.
        :param line: Line number.
        :returns: The location record, created on first use.
        """
        key = (file, line)
        location = self._by_location.get(key)
        if location is None:
            location = Location(key)
            self._by_location[key] = location
        return location

    def _claim_branches(self) -> None:
        """
        Split each branching line into what is emitted when, and tie it to the
        statement it belongs to.

        Instrumentation records every probe of a branching statement against
        the head line, but it injects them at three different points: in front
        of the statement, inside the body, and after it. In an instrumented run
        that is unambiguous because only the reached probes execute. A tracer
        sees one line and must reconstruct the split, which is what this does,
        once, at setup.

        A branch template with no matching statement -- an exception handler's,
        whose line runs on its own -- keeps being emitted directly.
        """
        for (file, line), location in self._by_location.items():
            branches = [
                template
                for template in location.templates
                if template.event_type is EventType.BRANCH
            ]
            loops = [
                template
                for template in location.templates
                if template.event_type
                in (EventType.LOOP_BEGIN, EventType.LOOP_HIT, EventType.LOOP_END)
            ]
            if not branches and not loops:
                continue
            site = self.structure.branch(file, line)
            if site is None:
                if len(branches) == 1:
                    try_site = self.structure.try_(file, line)
                    if try_site is not None:
                        location.completed = branches[0]
                        location.try_site = try_site
                        location.templates.remove(branches[0])
                continue
            location.site = site
            remaining: List[Event] = []
            # Lower id is the then-branch: instrumentation walks the then body
            # before the else body.
            branches.sort(key=lambda e: e.event_id)
            for template in location.templates:
                type_ = template.event_type
                if type_ is EventType.BRANCH:
                    if template is branches[0]:
                        location.on_body.append(template)
                    else:
                        location.on_exit.append(template)
                elif type_ is EventType.LOOP_HIT:
                    location.on_body.append(template)
                elif type_ is EventType.LOOP_END:
                    location.on_finally.append(template)
                elif site.loop and getattr(template, "var", None) in site.targets:
                    # The loop variable is bound once per iteration, inside the
                    # body, even though its probe is recorded on the head line.
                    location.on_body.append(template)
                else:
                    remaining.append(template)
            location.templates = remaining
            location.on_body.sort(key=lambda e: e.event_id)
            location.on_exit.sort(key=lambda e: e.event_id)
            location.on_finally.sort(key=lambda e: e.event_id)

    def _add_function_template(self, event: Event) -> None:
        """
        File one function-boundary template under its function.

        :param event: A function enter, exit or error template.
        """
        key = (event.file, event.function)
        candidates = self._functions.setdefault(key, [])
        # Templates of one function share a function_id; instrumentation
        # assigns a fresh one per function, so it separates same-named
        # functions (overloads, nested defs, methods) reliably.
        for templates in candidates:
            if templates.enter is not None and templates.enter.function_id == (
                event.function_id
            ):
                break
            if (
                templates.exits
                and next(iter(templates.exits.values())).function_id
                == event.function_id
            ):
                break
            if templates.error is not None and (
                templates.error.function_id == event.function_id
            ):
                break
        else:
            templates = FunctionTemplates()
            candidates.append(templates)
        if event.event_type is EventType.FUNCTION_ENTER:
            templates.enter = event
            templates.line = event.line
        elif event.event_type is EventType.FUNCTION_EXIT:
            templates.exits[event.line] = event
            templates.last_exit = event
            if not templates.line:
                templates.line = event.line
        else:
            templates.error = event
            if not templates.line:
                templates.line = event.line

    def relative(self, filename: str) -> Optional[str]:
        """
        Translate a runtime ``co_filename`` into the mapping's file name.

        :param filename: Filename as CPython reports it, absolute or relative.
        :returns: The mapping's name for that file, or ``None`` when the file
            carries no events. Cached, because this is asked once per location.
        """
        try:
            return self._resolved[filename]
        except KeyError:
            pass
        resolved: Optional[str] = None
        if filename in self.files:
            resolved = filename
        else:
            try:
                candidate = os.path.relpath(Path(filename).resolve(), self.root)
            except (OSError, ValueError):
                candidate = None
            if candidate in self.files:
                resolved = candidate
        self._resolved[filename] = resolved
        return resolved

    def at(self, file: str, line: int) -> Optional[Location]:
        """
        :param file: Mapping-relative file name.
        :param line: Line number.
        :returns: What is mapped there, or ``None``.
        """
        return self._by_location.get((file, line))

    def function(
        self, file: str, name: str, first_line: int
    ) -> Optional[FunctionTemplates]:
        """
        Find the templates of the function a code object belongs to.

        :param file: Mapping-relative file name.
        :param name: The code object's name.
        :param first_line: The code object's first line.
        :returns: The matching templates, or ``None``.

        Where a file holds several functions of the same name, the one whose
        probes sit closest below the code object's first line wins: probes are
        injected inside the body, so the correct function is always the nearest
        one at or after ``def``.
        """
        candidates = self._functions.get((file, name))
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        best = None
        for templates in candidates:
            if templates.line >= first_line and (
                best is None or templates.line < best.line
            ):
                best = templates
        return best or candidates[0]

    def has_events(self, file: str) -> bool:
        """
        :param file: Mapping-relative file name.
        :returns: Whether the file carries any event at all.
        """
        return file in self.files

    def __len__(self) -> int:
        return sum(
            len(location.templates)
            + len(location.on_body)
            + len(location.on_exit)
            + len(location.on_finally)
            + (1 if location.completed else 0)
            for location in self._by_location.values()
        ) + sum(len(candidates) for candidates in self._functions.values())


class Tracer(abc.ABC):
    """
    Shared materialization for the runtime backends.

    A backend only has to recognize interpreter callbacks and call
    :meth:`_line`, :meth:`_enter`, :meth:`_exit` and :meth:`_error`; turning a
    template plus a frame into an event happens here, once.

    :ivar index: Location index for the subject.
    :ivar listener: Where materialized events go.
    :ivar thread_ids: Compact thread-id source.
    """

    def __init__(
        self,
        index: LocationIndex,
        listener: EventListener,
        thread_support: bool = False,
    ):
        """
        :param index: Location index for the subject.
        :param listener: Listener or
            :class:`~sflkit.online.listener.ListenerGroup` to feed.
        :param thread_support: Stamp events with a compact thread id.
        """
        self.index = index
        self.listener = listener
        self.thread_ids = ThreadIds(thread_support)
        self._local = threading.local()
        self.running = False
        # The same budgets the instrumented runtime applies, read from the same
        # environment variables with the same defaults. Without them the two
        # collection paths disagree on any loop that runs more than twice: the
        # runtime stops recording hits and the tracer would keep going, so the
        # online spectra would be strictly richer than the offline ones and the
        # two would no longer be comparable.
        self.max_loop_hits = env_int("EVENTS_MAX_LOOP_HITS", 2)
        self.max_value_bytes = env_int("EVENTS_MAX_VALUE_BYTES", 1024)
        #: Hits recorded per thread per loop, keyed as the runtime keys them.
        self._loop_hits: Dict[Tuple[Optional[int], int], int] = dict()

    @property
    def _pending(self) -> Dict[Any, List[Event]]:
        """
        Def templates parked per frame, for the calling thread only.

        Instrumentation places a def probe *after* the assignment, but a line
        hook fires *before* the line runs, so at hook time the binding does not
        exist yet. The def is parked and materialized at the next hook for the
        same frame, which is the first moment the value is observable. Parking
        is per frame, not per thread, because ``x = f()`` parks in the caller
        while ``f`` runs in a frame of its own; and the state is thread-local,
        so concurrent threads never contend for it.
        """
        pending = getattr(self._local, "pending", None)
        if pending is None:
            pending = dict()
            self._local.pending = pending
        return pending

    @property
    def _parked_branches(self) -> Dict[Any, "Location"]:
        """
        Branch decisions waiting on the next line, per frame.

        Which side of a branch ran is only knowable once execution has moved
        on, so the decision is parked at the branching line and settled at the
        next line in the same frame -- or, if there is none, when the frame
        returns, which means the body was never entered.
        """
        parked = getattr(self._local, "branches", None)
        if parked is None:
            parked = dict()
            self._local.branches = parked
        return parked

    @property
    def _active_loops(self) -> Dict[Any, Dict[Tuple[str, int], "Location"]]:
        """Loops currently running, per frame, so a ``break`` is still noticed."""
        active = getattr(self._local, "loops", None)
        if active is None:
            active = dict()
            self._local.loops = active
        return active

    @property
    def _parked_tries(self) -> Dict[Any, List["Location"]]:
        """``try`` bodies currently executing, per frame."""
        parked = getattr(self._local, "tries", None)
        if parked is None:
            parked = dict()
            self._local.tries = parked
        return parked

    @abc.abstractmethod
    def start(self) -> None:
        """Install the backend's hooks."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Remove the backend's hooks."""

    def arm(self, code) -> None:
        """
        Watch *code* even though its call was not observed.

        Only meaningful for backends that monitor per code object.

        :param code: The code object to watch.
        """

    def __enter__(self) -> "Tracer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def _emit(self, event: Optional[Event]) -> None:
        """
        Hand one event to the listener, never letting a failure reach the
        program under test.

        :param event: The event, or ``None`` when it could not be materialized.
        """
        if event is None:
            return
        try:
            self.listener.event(event)
        except Exception:
            # A tracer must not change what the program does, so a broken
            # listener costs events rather than raising inside the subject.
            LOGGER.exception("Listener failed on %r", event)

    def _flush(self, frame: Any) -> None:
        """
        Materialize the def events parked for *frame*.

        :param frame: The frame whose parked defs are now observable.
        """
        pending = self._pending.pop(frame, None)
        if not pending:
            return
        thread_id = self.thread_ids.get()
        for template in pending:
            self._emit(self._def_event(template, frame, thread_id))

    def _line(self, frame: Any, file: str, line: int) -> None:
        """
        Handle one line about to execute.

        :param frame: The executing frame.
        :param file: Mapping-relative file name.
        :param line: The line number.
        """
        self._flush(frame)
        self._settle_branch(frame, line)
        self._settle_loops(frame, line)
        self._settle_tries(frame, line)
        location = self.index.at(file, line)
        if location is None:
            return
        thread_id = self.thread_ids.get()
        site = location.site
        arriving = True
        if site is not None and site.loop:
            active = self._active_loops.setdefault(frame, dict())
            arriving = location.key not in active
            active[location.key] = location
        if arriving:
            # A loop head runs once per iteration, but what is mapped to it
            # outside the body -- the loop-begin probe, the line, the uses in
            # the iterable -- was hoisted in front of the loop and runs once.
            self._emit_templates(location.templates, frame, thread_id, park=True)
        if site is not None:
            self._parked_branches[frame] = location
        if location.completed is not None:
            self._parked_tries.setdefault(frame, []).append(location)

    def _emit_templates(
        self, templates: List[Event], frame: Any, thread_id, park: bool
    ) -> None:
        """
        Materialize and emit *templates* against *frame*.

        :param frame: The executing frame.
        :param thread_id: Compact id of the current thread.
        :param park: Whether def templates are parked for the next hook. They
            are, for a line about to run; they are not for the group settled
            once a loop body has been entered, because the loop variable is
            already bound by then.
        """
        for template in templates:
            type_ = template.event_type
            if type_ is EventType.DEF:
                if park:
                    self._pending.setdefault(frame, []).append(template)
                else:
                    self._emit(self._def_event(template, frame, thread_id))
            elif type_ is EventType.USE:
                self._emit(self._use_event(template, frame, thread_id))
            elif type_ is EventType.LEN:
                self._emit(self._len_event(template, frame, thread_id))
            elif type_ is EventType.LOOP_HIT:
                if self._record_loop_hit(template, thread_id):
                    self._emit(template.instantiate(thread_id))
            else:
                self._emit(template.instantiate(thread_id))

    def _record_loop_hit(self, template: Event, thread_id) -> bool:
        """
        Count one hit of a loop and say whether it is still worth recording.

        :param template: The loop-hit template.
        :param thread_id: The thread the hit happened on.
        :returns: Whether to emit the event.

        Mirrors ``sflkitlib.lib.add_loop_hit_event``: sflkit distinguishes only
        never, once and more-than-once, so hits beyond the budget carry no
        information. The count is keyed by thread and hit event, exactly as the
        runtime keys it, which means it is not reset when the loop is re-entered
        -- matching the runtime matters more here than being tidy, because the
        two have to produce the same events.
        """
        if self.max_loop_hits <= 0:
            return True
        key = (thread_id, template.event_id)
        hits = self._loop_hits.get(key, 0) + 1
        self._loop_hits[key] = hits
        return hits <= self.max_loop_hits

    def _settle_loops(self, frame: Any, line: int) -> None:
        """
        Close every loop *frame* has left without passing its head again.

        :param frame: The executing frame.
        :param line: The line now running.

        This is what a ``break`` looks like from outside: control leaves the
        body without the head ever running again, so the loop's end is only
        detectable by noticing that execution is no longer inside it.
        """
        active = self._active_loops.get(frame)
        if not active:
            return
        thread_id = self.thread_ids.get()
        for key, location in list(active.items()):
            if not location.site.owns(line):
                del active[key]
                self._emit_templates(location.on_finally, frame, thread_id, park=False)
        if not active:
            self._active_loops.pop(frame, None)

    def _settle_branch(self, frame: Any, line: int) -> None:
        """
        Emit what the parked statement in *frame* turned out to do.

        :param frame: The executing frame.
        :param line: The line now running, which is what decides it. ``-1``
            means no line follows, so no body was entered.
        """
        location = self._parked_branches.pop(frame, None)
        if location is None:
            return
        thread_id = self.thread_ids.get()
        if location.site.taken(line):
            self._emit_templates(location.on_body, frame, thread_id, park=False)
            return
        self._emit_templates(location.on_exit, frame, thread_id, park=False)
        if location.site.loop:
            active = self._active_loops.get(frame)
            if active is not None:
                active.pop(location.key, None)
            self._emit_templates(location.on_finally, frame, thread_id, park=False)

    def _settle_tries(self, frame: Any, line: int) -> None:
        """
        Emit the completion of every ``try`` body *frame* has just left.

        :param frame: The executing frame.
        :param line: The line now running.
        """
        parked = self._parked_tries.get(frame)
        if not parked:
            return
        thread_id = self.thread_ids.get()
        remaining = []
        for location in parked:
            if line in location.try_site.body:
                remaining.append(location)
            else:
                # Leaving the body by running past it means it did not raise.
                self._emit(location.completed.instantiate(thread_id))
        if remaining:
            self._parked_tries[frame] = remaining
        else:
            self._parked_tries.pop(frame, None)

    def _settle_tries_on_exit(self, frame: Any) -> None:
        """
        Resolve ``try`` bodies still parked when *frame* returns.

        A body that ends in ``return`` never reaches the probe appended after
        it, so nothing is due; a body that simply runs out at the end of the
        function does reach it.

        :param frame: The returning frame.
        """
        parked = self._parked_tries.pop(frame, None)
        if not parked:
            return
        thread_id = self.thread_ids.get()
        for location in parked:
            if location.try_site.completes:
                self._emit(location.completed.instantiate(thread_id))

    def _enter(self, frame: Any, file: str, name: str, first_line: int) -> None:
        """
        Handle a function being entered.

        :param frame: The new frame.
        :param file: Mapping-relative file name.
        :param name: The code object's name.
        :param first_line: The code object's first line.
        """
        templates = self.index.function(file, name, first_line)
        if templates is None or templates.enter is None:
            return
        thread_id = self.thread_ids.get()
        self._emit(templates.enter.instantiate(thread_id))
        # Parameters are bound before the first line of the body runs, so they
        # are read now rather than parked like an ordinary def.
        for template in templates.parameters:
            if template.event_type is EventType.DEF:
                self._emit(self._def_event(template, frame, thread_id))
            elif template.event_type is EventType.USE:
                self._emit(self._use_event(template, frame, thread_id))
            else:
                self._emit(self._len_event(template, frame, thread_id))

    def _exit(
        self, frame: Any, file: str, name: str, first_line: int, value: Any
    ) -> None:
        """
        Handle a function returning.

        :param frame: The returning frame.
        :param file: Mapping-relative file name.
        :param name: The code object's name.
        :param first_line: The code object's first line.
        :param value: The returned value.
        """
        self._flush(frame)
        # No further line will run in this frame, so a branch still parked was
        # one whose body was never entered.
        self._settle_branch(frame, -1)
        self._settle_loops(frame, -1)
        self._settle_tries_on_exit(frame)
        templates = self.index.function(file, name, first_line)
        if templates is None:
            return
        template = templates.exits.get(frame.f_lineno) or templates.last_exit
        if template is None:
            return
        payload, type_name = value_and_type(value, self.max_value_bytes)
        self._emit(template.instantiate(payload, type_name, self.thread_ids.get()))

    def _error(self, frame: Any, file: str, name: str, first_line: int) -> None:
        """
        Handle a function leaving through an exception.

        :param frame: The unwinding frame.
        :param file: Mapping-relative file name.
        :param name: The code object's name.
        :param first_line: The code object's first line.
        """
        # Nothing parked in a frame that is being torn down is observable: the
        # probes instrumentation would have run are all past the raise.
        self._pending.pop(frame, None)
        self._parked_branches.pop(frame, None)
        self._parked_tries.pop(frame, None)
        # The loop-end probe sits in a finally, so it runs even while an
        # exception is unwinding the frame.
        self._settle_loops(frame, -1)
        templates = self.index.function(file, name, first_line)
        if templates is None or templates.error is None:
            return
        self._emit(templates.error.instantiate(self.thread_ids.get()))

    def _resolve(self, frame: Any, name: str) -> Tuple[bool, Any]:
        """
        Look *name* up in *frame*, following a dotted path.

        :param frame: Frame to resolve against.
        :param name: A variable name, possibly dotted (``self.x``).
        :returns: ``(found, value)``. Resolution never raises: any failure
            reports not-found, because a probe that changes the program is
            worse than a missing event.
        """
        head, *rest = name.split(".")
        try:
            local = frame.f_locals
            if head in local:
                value = local[head]
            elif head in frame.f_globals:
                value = frame.f_globals[head]
            else:
                # Builtins are the third and last scope Python itself consults,
                # and instrumentation records uses of them (`int`, `len`) like
                # any other name.
                builtins = frame.f_builtins
                if head in builtins:
                    value = builtins[head]
                else:
                    return False, None
            for attribute in rest:
                value = getattr(value, attribute)
        except Exception:
            return False, None
        return True, value

    def _def_event(self, template: Event, frame: Any, thread_id) -> Optional[Event]:
        """Materialize a ``DEF`` event, or ``None`` when the name is not bound."""
        found, value = self._resolve(frame, template.var)
        if not found:
            return None
        payload, type_name = value_and_type(value, self.max_value_bytes)
        return template.instantiate(id(value), payload, type_name, thread_id)

    def _use_event(self, template: Event, frame: Any, thread_id) -> Optional[Event]:
        """Materialize a ``USE`` event, or ``None`` when the name is not bound."""
        found, value = self._resolve(frame, template.var)
        if not found:
            return None
        return template.instantiate(id(value), thread_id)

    def _len_event(self, template: Event, frame: Any, thread_id) -> Optional[Event]:
        """Materialize a ``LEN`` event, or ``None`` when there is no length."""
        found, value = self._resolve(frame, template.var)
        if not found:
            return None
        try:
            length = len(value)
        except Exception:
            return None
        return template.instantiate(id(value), length, thread_id)


class MonitoringTracer(Tracer):
    """
    Backend built on :mod:`sys.monitoring` (PEP 669), Python 3.12 and newer.

    Cheaper than :func:`sys.settrace` in two ways that matter for tracing a
    whole test suite. Event types are opted into individually, so nothing pays
    for events sflkit does not want. And a line in a file that carries no
    events is disabled the first time it is reached, after which the
    interpreter stops calling back for it entirely, so library code costs one
    callback per location for the lifetime of the process rather than one per
    execution.

    Lines inside mapped files stay enabled even when nothing is mapped to them,
    because a parked def becomes observable at the next hook for its frame and
    disabling those lines would delay it.

    Monitoring is process-wide, so every thread is observed without extra work.
    """

    #: Tool ids tried in order. coverage.py claims ``COVERAGE_ID``, so that one
    #: is left alone: sflkit's own suite runs under pytest-cov.
    _TOOL_IDS = (
        sys.monitoring.PROFILER_ID if hasattr(sys, "monitoring") else 2,
        sys.monitoring.DEBUGGER_ID if hasattr(sys, "monitoring") else 0,
        sys.monitoring.OPTIMIZER_ID if hasattr(sys, "monitoring") else 5,
    )

    def __init__(
        self,
        index: LocationIndex,
        listener: EventListener,
        thread_support: bool = False,
    ):
        super().__init__(index, listener, thread_support=thread_support)
        self.tool_id: Optional[int] = None
        #: Code objects already switched to line-level monitoring.
        self._instrumented: Set[Any] = set()

    @staticmethod
    def available() -> bool:
        """:returns: Whether this backend can run on the current interpreter."""
        return hasattr(sys, "monitoring")

    def _acquire_tool_id(self) -> int:
        """
        Claim a monitoring tool id.

        :returns: The claimed id.
        :raises RuntimeError: When every candidate id is already in use, which
            means another tool (a debugger, a profiler, coverage) holds them.
        """
        for tool_id in self._TOOL_IDS:
            try:
                sys.monitoring.use_tool_id(tool_id, "sflkit")
            except ValueError:
                continue
            return tool_id
        raise RuntimeError(
            "No free sys.monitoring tool id; another tracing tool is active"
        )

    def start(self) -> None:
        if self.running:
            return
        events = sys.monitoring.events
        self.tool_id = self._acquire_tool_id()
        sys.monitoring.register_callback(self.tool_id, events.LINE, self._on_line)
        sys.monitoring.register_callback(self.tool_id, events.PY_START, self._on_start)
        sys.monitoring.register_callback(
            self.tool_id, events.PY_RETURN, self._on_return
        )
        sys.monitoring.register_callback(
            self.tool_id, events.PY_UNWIND, self._on_unwind
        )
        # Only PY_START is global. Enabling LINE globally would instrument
        # every code object in the process, including sflkit's own analysis
        # running in this very process, and instrumented bytecode stays slower
        # even once a location has been disabled. Line events are therefore
        # switched on per code object, at the first call into a mapped file.
        sys.monitoring.set_events(self.tool_id, events.PY_START | events.PY_UNWIND)
        self.running = True
        # Frames already on the stack will never report a call, so arm them
        # now: a tracer started from inside subject code (a pytest plugin, a
        # harness) would otherwise miss the rest of the enclosing frames.
        frame = sys._getframe(1)
        while frame is not None:
            self.arm(frame.f_code)
            frame = frame.f_back

    def arm(self, code) -> None:
        """
        Switch *code* to line-level monitoring straight away.

        Module-level code is already running by the time a tracer starts inside
        it, so it never reports a call and would otherwise stay unwatched.

        :param code: The code object to watch.
        """
        if not self.running or code in self._instrumented:
            return
        if self.index.relative(code.co_filename) is None:
            return
        self._instrumented.add(code)
        events = sys.monitoring.events
        sys.monitoring.set_local_events(
            self.tool_id, code, events.LINE | events.PY_RETURN
        )

    def stop(self) -> None:
        if not self.running:
            return
        events = sys.monitoring.events
        for code in self._instrumented:
            sys.monitoring.set_local_events(self.tool_id, code, 0)
        self._instrumented.clear()
        sys.monitoring.set_events(self.tool_id, 0)
        for event in (events.LINE, events.PY_START, events.PY_RETURN, events.PY_UNWIND):
            sys.monitoring.register_callback(self.tool_id, event, None)
        sys.monitoring.free_tool_id(self.tool_id)
        self.tool_id = None
        self.running = False

    def _on_line(self, code, line_number):
        file = self.index.relative(code.co_filename)
        if file is None:
            # Nothing in this file is ever interesting: stop calling us here.
            return sys.monitoring.DISABLE
        self._line(sys._getframe(1), file, line_number)
        return None

    def _on_start(self, code, instruction_offset):
        file = self.index.relative(code.co_filename)
        if file is None:
            return sys.monitoring.DISABLE
        if code not in self._instrumented:
            self._instrumented.add(code)
            events = sys.monitoring.events
            sys.monitoring.set_local_events(
                self.tool_id, code, events.LINE | events.PY_RETURN
            )
        self._enter(sys._getframe(1), file, code.co_name, code.co_firstlineno)
        return None

    def _on_return(self, code, instruction_offset, retval):
        file = self.index.relative(code.co_filename)
        if file is None:
            return sys.monitoring.DISABLE
        self._exit(sys._getframe(1), file, code.co_name, code.co_firstlineno, retval)
        return None

    def _on_unwind(self, code, instruction_offset, exception):
        file = self.index.relative(code.co_filename)
        if file is None:
            # PY_UNWIND is not a local event, so it cannot be disabled per
            # location: returning DISABLE here drops the callback entirely.
            return None
        self._error(sys._getframe(1), file, code.co_name, code.co_firstlineno)
        return None


class SysTraceTracer(Tracer):
    """
    Backend built on :func:`sys.settrace`, for interpreters without
    :mod:`sys.monitoring`.

    Correct everywhere sflkit runs, but it pays a Python-level callback for
    every executed line of every traced frame, so it is the fallback rather
    than the default.

    :func:`threading.settrace` is installed as well, so threads started while
    tracing are observed. Threads already running when :meth:`start` is called
    cannot be hooked: CPython offers no way to install a trace function into
    another live thread.
    """

    def __init__(
        self,
        index: LocationIndex,
        listener: EventListener,
        thread_support: bool = False,
    ):
        super().__init__(index, listener, thread_support=thread_support)
        self._previous = None

    @staticmethod
    def available() -> bool:
        """:returns: Always ``True``; this backend is the portable one."""
        return True

    def start(self) -> None:
        if self.running:
            return
        self._previous = sys.gettrace()
        threading.settrace(self._dispatch)
        sys.settrace(self._dispatch)
        self.running = True

    def stop(self) -> None:
        if not self.running:
            return
        sys.settrace(self._previous)
        threading.settrace(None)
        self._previous = None
        self.running = False

    @property
    def _raised(self) -> Set[Any]:
        """
        Frames that have seen an exception, per thread.

        ``settrace`` reports a frame leaving through an exception as a plain
        ``return`` with ``None``, so the preceding ``exception`` event is what
        distinguishes an error exit from an ordinary one.
        """
        raised = getattr(self._local, "raised", None)
        if raised is None:
            raised = set()
            self._local.raised = raised
        return raised

    def _dispatch(self, frame, event, arg):
        """
        The trace function.

        :param frame: The frame the event belongs to.
        :param event: ``call``, ``line``, ``return`` or ``exception``.
        :param arg: Event-specific payload.
        :returns: Itself for frames worth tracing, ``None`` otherwise, which is
            how CPython is told to stop tracing a frame.
        """
        code = frame.f_code
        file = self.index.relative(code.co_filename)
        if file is None:
            return None
        if event == "call":
            self._enter(frame, file, code.co_name, code.co_firstlineno)
        elif event == "line":
            self._line(frame, file, frame.f_lineno)
        elif event == "exception":
            self._raised.add(id(frame))
        elif event == "return":
            if id(frame) in self._raised:
                self._raised.discard(id(frame))
                # arg is None for a frame unwound by an exception; a genuine
                # `return None` would have cleared the flag at the next line.
                if arg is None:
                    self._error(frame, file, code.co_name, code.co_firstlineno)
                    return self._dispatch
            self._exit(frame, file, code.co_name, code.co_firstlineno, arg)
        return self._dispatch

    def _line(self, frame: Any, file: str, line: int) -> None:
        # Reaching a new line means any exception raised earlier in this frame
        # was handled, so the frame is no longer unwinding.
        self._raised.discard(id(frame))
        super()._line(frame, file, line)


def get_tracer(
    index: LocationIndex,
    listener: EventListener,
    thread_support: bool = False,
    prefer_monitoring: bool = True,
) -> Tracer:
    """
    Build the best available tracer for this interpreter.

    :param index: Location index for the subject.
    :param listener: Listener to feed.
    :param thread_support: Stamp events with a compact thread id.
    :param prefer_monitoring: Set to ``False`` to force the portable
        :func:`sys.settrace` backend, which the tests use to exercise both
        backends on one interpreter.
    :returns: A :class:`MonitoringTracer` on Python 3.12+, otherwise a
        :class:`SysTraceTracer`.
    """
    if prefer_monitoring and MonitoringTracer.available():
        return MonitoringTracer(index, listener, thread_support=thread_support)
    return SysTraceTracer(index, listener, thread_support=thread_support)
