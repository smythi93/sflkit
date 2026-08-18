"""
Listeners that build analysis artifacts while the program under test runs.

The offline pipeline serializes every event to disk and reads the whole trace
back to build spectra, feature vectors and relevance trees.  A listener
consumes the same :class:`~sflkitlib.events.event.Event` objects as they are
produced, so the artifact is finished the moment the run terminates: nothing is
written and nothing is read back.

Listeners are deliberately thin.  Each owns a :class:`~sflkit.model.model.Model`
and feeds it exactly what :meth:`sflkit.analysis.analyzer.Analyzer._analyze`
feeds it offline -- ``prepare``, one ``handle`` per event, ``follow_up`` -- so
the analysis layer cannot tell the two sources apart and every spectrum,
predicate and feature keeps its offline meaning.  That is what makes the two
workflows comparable: an online artifact is not an approximation of the offline
one, it is the same computation with the disk round-trip removed.
"""

import abc
from typing import Iterable, List, Optional, Set

from sflkitlib.events.event import Event

from sflkit.analysis.analysis_type import AnalysisObject, AnalysisType
from sflkit.analysis.factory import (
    AnalysisFactory,
    CombinationFactory,
    analysis_factory_mapping,
)
from sflkit.events.event_file import EventFile
from sflkit.features.handler import EventHandler, FeatureBuilder
from sflkit.model.model import Model
from sflkit.model.parallel import ParallelModel


class OnlineError(RuntimeError):
    """Raised when a listener is driven out of order."""


def spectrum_factory(
    types: Optional[Iterable[AnalysisType]] = None,
) -> AnalysisFactory:
    """
    Build the analysis factory for *types*, or for every analysis type.

    :param types: Analysis types to collect.  ``None`` collects all of them,
        which is what :class:`~sflkit.features.handler.FeatureBuilder` does.
    :returns: A factory combining one sub-factory per requested type.
    """
    if types is None:
        types = analysis_factory_mapping.keys()
    return CombinationFactory([analysis_factory_mapping[t]() for t in types])


class EventListener(abc.ABC):
    """
    Receives a run's events as they happen.

    The contract is a single run: :meth:`start`, any number of :meth:`event`
    calls, then :meth:`stop`.  A listener may be reused for the next run after
    :meth:`stop` returns.
    """

    def start(self, run: EventFile) -> None:
        """
        Begin a run.

        :param run: Identity of the run about to be traced.  This is an
            :class:`~sflkit.events.event_file.EventFile` even though no file is
            involved: the analysis layer keys all of its per-run state by it,
            and it is never opened, so it costs nothing to reuse the type
            rather than introduce a parallel one that every ``dict`` would then
            have to accept.
        """

    @abc.abstractmethod
    def event(self, event: Event) -> None:
        """
        Consume one event of the current run.

        :param event: A fully instantiated event, indistinguishable from one
            decoded off a trace file.
        """

    def stop(self) -> None:
        """Finish the current run."""


class ModelListener(EventListener):
    """
    Drives a :class:`~sflkit.model.model.Model` from a live event stream.

    :ivar factory: The analysis factory the model dispatches to.
    :ivar model: Serial or parallel model, depending on ``thread_support``.
    :ivar run: The run currently being traced, or ``None`` between runs.
    """

    def __init__(
        self,
        factory: AnalysisFactory,
        thread_support: bool = False,
        workers: int = 4,
    ):
        """
        :param factory: Analysis factory to dispatch events to.
        :param thread_support: Use :class:`~sflkit.model.parallel.ParallelModel`,
            which keeps one scope per thread id.
        :param workers: Worker threads used when finalizing analysis objects.
        """
        self.factory = factory
        self.thread_support = thread_support
        self.model: Model = (
            ParallelModel(factory, workers=workers)
            if thread_support
            else Model(factory, workers=workers)
        )
        self.run: Optional[EventFile] = None

    def start(self, run: EventFile) -> None:
        self.run = run
        self.model.prepare(run)

    def event(self, event: Event) -> None:
        if self.run is None:
            raise OnlineError("event() before start(): no run is being traced")
        event.handle(self.model, self.run)

    def stop(self) -> None:
        if self.run is None:
            return
        self.model.follow_up(self.run)
        self.run = None


class SpectrumListener(ModelListener):
    """
    Builds spectra and predicates online, the way
    :class:`~sflkit.analysis.analyzer.Analyzer` builds them offline.

    Suspiciousness is a whole-suite property, so it is not available until
    every run has been seen: call :meth:`finalize` once, with all runs, before
    reading :attr:`analysis`.
    """

    def __init__(
        self,
        types: Optional[Iterable[AnalysisType]] = None,
        factory: Optional[AnalysisFactory] = None,
        thread_support: bool = False,
        workers: int = 4,
    ):
        """
        :param types: Analysis types to collect.  Ignored when *factory* is given.
        :param factory: Pre-built factory, e.g. ``config.factory``.
        :param thread_support: See :class:`ModelListener`.
        :param workers: See :class:`ModelListener`.
        """
        super().__init__(
            factory if factory is not None else spectrum_factory(types),
            thread_support=thread_support,
            workers=workers,
        )

    @property
    def analysis(self) -> Set[AnalysisObject]:
        """Every analysis object observed so far, across all runs."""
        return self.model.get_analysis()

    def finalize(
        self,
        passing: Optional[List[EventFile]] = None,
        failing: Optional[List[EventFile]] = None,
    ) -> None:
        """
        Compute suspiciousness over the collected runs.

        :param passing: The passing runs.
        :param failing: The failing runs.
        """
        self.model.finalize(passing, failing)


class BuilderListener(ModelListener):
    """
    Builds feature vectors online, and anything else a
    :class:`~sflkit.features.handler.FeatureBuilder` subclass builds.

    FORECAST's ``TreeBuilder`` is such a subclass, so passing one here builds
    the relevance tree during execution instead of from event files; this
    listener calls its ``post_process`` hook on :meth:`stop` exactly as
    ``ForecastHandler.handle`` calls it after draining an event file.

    :ivar builder: The builder receiving ``prepare``/``hit``/``post_process``.
    """

    def __init__(
        self,
        builder: Optional[FeatureBuilder] = None,
        thread_support: bool = False,
        workers: int = 4,
    ):
        """
        :param builder: Builder to drive.  Defaults to a plain
            :class:`~sflkit.features.handler.FeatureBuilder`, which yields one
            feature vector per run.
        :param thread_support: See :class:`ModelListener`.
        :param workers: See :class:`ModelListener`.
        """
        self.builder = builder if builder is not None else FeatureBuilder()
        super().__init__(self.builder, thread_support=thread_support, workers=workers)

    def start(self, run: EventFile) -> None:
        super().start(run)
        self.builder.prepare(run, EventHandler.map_result(run.failing))

    def stop(self) -> None:
        run = self.run
        super().stop()
        # TreeBuilder records the root exit vector here; FeatureBuilder has no
        # such hook. Mirrors ForecastHandler.handle, which post-processes after
        # the event loop rather than inside it.
        post_process = getattr(self.builder, "post_process", None)
        if run is not None and post_process is not None:
            post_process(run)


class ListenerGroup(EventListener):
    """
    Fans one event stream out to several listeners.

    This is what makes "all at the same time" cheap: spectra, feature vectors
    and the relevance tree are built from a single execution, because the cost
    that dominates is producing the events, not consuming them.

    :ivar listeners: The listeners, notified in order.
    """

    def __init__(self, *listeners: EventListener):
        """
        :param listeners: Listeners to drive, in order.
        """
        self.listeners: List[EventListener] = list(listeners)

    def add(self, listener: EventListener) -> EventListener:
        """
        Append *listener* to the group.

        :param listener: The listener to add.
        :returns: The listener, so callers can keep a handle on it inline.
        """
        self.listeners.append(listener)
        return listener

    def start(self, run: EventFile) -> None:
        for listener in self.listeners:
            listener.start(run)

    def event(self, event: Event) -> None:
        for listener in self.listeners:
            listener.event(event)

    def stop(self) -> None:
        # Reverse order so a listener that wraps another still sees a live
        # inner listener while finishing up.
        for listener in reversed(self.listeners):
            listener.stop()
