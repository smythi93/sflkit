"""
Driving a traced run and shipping what it produced.

Collectors live inside the process that runs the test, so a run ends with the
artifact already built. What crosses the process boundary afterwards is that
artifact -- a per-run feature record and, optionally, a call tree -- rather
than a raw event stream. The size difference is the point: a trace grows with
the number of events executed, an artifact with the number of program points
observed.

Typical use inside the test process::

    with trace(mapping, root, name=test, failing=True) as session:
        run_the_test()
    session.artifact().dump(out / test)

and in the parent, once every test has run::

    suite = Suite.merge(RunArtifact.load(p) for p in paths)
"""

import gzip
import os
import pickle
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sflkit.analysis.analysis_type import AnalysisType
from sflkit.events.event_file import EventFile
from sflkit.events.mapping import EventMapping
from sflkit.features.value import FeatureValue
from sflkit.online.listener import (
    BuilderListener,
    ListenerGroup,
    SpectrumListener,
)
from sflkit.online.tracer import LocationIndex, Tracer, get_tracer
from sflkit.online.tree import TreeBuilder, TreeNode
from sflkit.runners.run import TestResult

#: Leading bytes of a gzip stream, used to detect compressed artifacts.
_GZIP_MAGIC = b"\x1f\x8b"


class RunArtifact:
    """
    Everything one traced run contributes to the analysis.

    :ivar run: Name of the run, usually the test id.
    :ivar result: Whether the run passed, failed, or neither.
    :ivar features: Feature id to :class:`~sflkit.features.value.FeatureValue`
        value observed in this run. This single record serves both purposes:
        it is the run's feature vector, and it is the per-run spectrum from
        which pass/fail counts are aggregated.
    :ivar catalog: Feature id to feature name.
    :ivar tree: The run's call tree, when one was built.
    """

    def __init__(
        self,
        run: str,
        result: TestResult,
        features: Dict[int, int],
        catalog: Dict[int, str],
        tree: Optional[TreeNode] = None,
    ):
        self.run = run
        self.result = result
        self.features = features
        self.catalog = catalog
        self.tree = tree

    def __repr__(self):
        return (
            f"RunArtifact({self.run}, {self.result.name}, "
            f"features={len(self.features)})"
        )

    def dump(self, path: os.PathLike | str, compress: bool = True) -> None:
        """
        Write the artifact to *path*.

        :param path: Destination.
        :param compress: gzip the pickle, which is worth it because feature
            records repeat heavily across runs.

        The write is atomic: a killed process leaves either the previous
        artifact or nothing, never a plausible-looking truncated one.
        """
        opener = gzip.open if compress else open
        target = os.fspath(path)
        tmp = f"{target}.tmp"
        try:
            with opener(tmp, "wb") as fp:
                pickle.dump(self, fp)
            os.replace(tmp, target)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @staticmethod
    def load(path: os.PathLike | str) -> "RunArtifact":
        """
        Read an artifact written by :meth:`dump`.

        :param path: The artifact file. The codec is detected from its magic
            bytes, so compressed and plain artifacts are read transparently.
        :returns: The artifact.
        """
        with open(path, "rb") as fp:
            header = fp.read(2)
        opener = gzip.open if header.startswith(_GZIP_MAGIC) else open
        with opener(path, "rb") as fp:
            return pickle.load(fp)


class Suite:
    """
    The merge of every run's artifact.

    :ivar runs: The per-run records, failing runs first.
    :ivar catalog: Feature id to name, unioned over all runs.
    :ivar tree: The merged call tree, or ``None`` when no run built one.
    """

    def __init__(
        self,
        runs: List[RunArtifact],
        catalog: Dict[int, str],
        tree: Optional[TreeNode] = None,
    ):
        self.runs = runs
        self.catalog = catalog
        self.tree = tree

    @staticmethod
    def merge(artifacts: Iterable[RunArtifact]) -> "Suite":
        """
        Merge run artifacts into one suite.

        :param artifacts: The artifacts, in any order.
        :returns: The merged suite.

        Failing runs are merged first and kept first. Tree consumers prune
        passing runs against the failing footprint -- a function no failing run
        ever reached cannot discriminate -- and that only works if the failing
        side of the tree exists before the passing runs are folded in. Ordering
        here means the collector does not need to know which tests fail before
        it runs them.
        """
        ordered = sorted(
            artifacts, key=lambda a: 0 if a.result == TestResult.FAILING else 1
        )
        catalog: Dict[int, str] = dict()
        tree: Optional[TreeNode] = None
        for artifact in ordered:
            catalog.update(artifact.catalog)
            if artifact.tree is not None:
                if tree is None:
                    tree = TreeNode(artifact.tree.name)
                tree.merge(artifact.tree)
        return Suite(ordered, catalog, tree)

    def name(self, feature_id: int) -> str:
        """
        :param feature_id: A feature id.
        :returns: The feature's name, or its id as a string when unknown.
        """
        return self.catalog.get(feature_id, str(feature_id))

    def counts(self) -> Dict[int, Dict[str, int]]:
        """
        Aggregate the per-run records into spectrum counts.

        :returns: Feature id to ``{"ef", "nf", "ep", "np"}``: runs where the
            feature held (``e``) or did not (``n``), failing (``f``) or passing
            (``p``). These are the four numbers every similarity coefficient in
            :mod:`sflkit.analysis.spectra` is defined over.
        """
        counts: Dict[int, Dict[str, int]] = {
            feature_id: {"ef": 0, "nf": 0, "ep": 0, "np": 0}
            for feature_id in self.catalog
        }
        for artifact in self.runs:
            if artifact.result == TestResult.FAILING:
                hit, missed = "ef", "nf"
            elif artifact.result == TestResult.PASSING:
                hit, missed = "ep", "np"
            else:
                continue
            for feature_id in counts:
                value = artifact.features.get(feature_id, FeatureValue.UNDEFINED.value)
                counts[feature_id][
                    hit if value == FeatureValue.TRUE.value else missed
                ] += 1
        return counts


class OnlineSession:
    """
    Ties a tracer to the listeners that consume its events.

    :ivar index: Location index for the subject.
    :ivar builder: The feature (and optionally tree) builder.
    :ivar spectra: Spectrum listener, when spectra were requested.
    :ivar listeners: Everything fed from the run.
    :ivar tracer: The runtime backend.
    """

    def __init__(
        self,
        mapping: Optional[EventMapping] = None,
        root: Optional[os.PathLike | str] = None,
        thread_support: bool = False,
        tree: bool = True,
        spectra: bool = False,
        types: Optional[Iterable[AnalysisType]] = None,
        prefer_monitoring: bool = True,
        index: Optional[LocationIndex] = None,
    ):
        """
        :param mapping: Event mapping produced by instrumentation. Not needed
            when *index* is given.
        :param root: Directory the mapping's file names are relative to.
        :param thread_support: Trace threads and key scopes by thread id.
        :param tree: Build a mergeable call tree alongside the feature vector.
        :param spectra: Also build spectra and predicates in this process,
            which is only useful when one process runs several tests.
        :param types: Analysis types for the spectrum listener.
        :param prefer_monitoring: Force the portable backend when ``False``.
        :param index: A location index to reuse. Building one parses every
            mapped source file, so a process running many tests builds it once
            and hands it to each run's session.
        """
        if index is None:
            if mapping is None or root is None:
                raise ValueError("Either an index or a mapping and root are required")
            index = LocationIndex(mapping, root)
        self.index = index
        self.builder = TreeBuilder() if tree else None
        self.vectors = BuilderListener(
            builder=self.builder, thread_support=thread_support
        )
        self.spectra = (
            SpectrumListener(types=types, thread_support=thread_support)
            if spectra
            else None
        )
        self.listeners = ListenerGroup(self.vectors)
        if self.spectra is not None:
            self.listeners.add(self.spectra)
        self.tracer: Tracer = get_tracer(
            self.index,
            self.listeners,
            thread_support=thread_support,
            prefer_monitoring=prefer_monitoring,
        )
        self._run: Optional[EventFile] = None
        self._name: str = ""

    def start(self, name: str, failing: Optional[bool] = None, run_id: int = 0) -> None:
        """
        Begin tracing a run.

        :param name: Name of the run, usually the test id.
        :param failing: Whether the run fails. ``None`` records it as undefined,
            which is the honest value while the verdict is still unknown.
        :param run_id: Identifier, only needs to be unique within the process.
        """
        self._name = name
        # EventFile is the analysis layer's per-run key everywhere; it is never
        # opened here, so reusing it costs nothing and avoids a parallel type.
        self._run = EventFile(Path(name), run_id, None, failing)
        self.listeners.start(self._run)
        self.tracer.start()

    def stop(self) -> None:
        """Stop tracing and finish the run."""
        self.tracer.stop()
        self.listeners.stop()

    def artifact(self) -> RunArtifact:
        """
        :returns: What this run contributes to the analysis.
        :raises ValueError: When no run has been traced yet.
        """
        if self._run is None:
            raise ValueError("No run has been traced")
        vector = self.vectors.builder.feature_vectors[self._run]
        features = dict()
        catalog = dict()
        for feature, value in vector.get_features().items():
            features[feature.id] = value.value
            catalog[feature.id] = feature.name
        if self.builder is not None:
            catalog.update(self.builder.catalog)
        return RunArtifact(
            self._name,
            vector.result,
            features,
            catalog,
            self.builder.root if self.builder is not None else None,
        )


@contextmanager
def trace(
    mapping: EventMapping,
    root: os.PathLike | str,
    name: str = "run",
    failing: Optional[bool] = None,
    thread_support: bool = False,
    tree: bool = True,
    spectra: bool = False,
    types: Optional[Iterable[AnalysisType]] = None,
    prefer_monitoring: bool = True,
):
    """
    Trace everything executed in the block.

    :param mapping: Event mapping produced by instrumentation.
    :param root: Directory the mapping's file names are relative to.
    :param name: Name of the run.
    :param failing: Whether the run fails, when already known.
    :param thread_support: Trace threads and key scopes by thread id.
    :param tree: Build a mergeable call tree.
    :param spectra: Also build spectra and predicates.
    :param types: Analysis types for the spectrum listener.
    :param prefer_monitoring: Force the portable backend when ``False``.
    :yields: The :class:`OnlineSession`, so the caller can take its artifact.
    """
    session = OnlineSession(
        mapping,
        root,
        thread_support=thread_support,
        tree=tree,
        spectra=spectra,
        types=types,
        prefer_monitoring=prefer_monitoring,
    )
    session.start(name, failing=failing)
    try:
        yield session
    finally:
        session.stop()
