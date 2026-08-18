import os.path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import List, Dict, Set, Optional

from sflkitlib.events.event import Event

from sflkit.analysis.analysis_type import AnalysisObject, EvaluationResult
from sflkit.analysis.factory import CombinationFactory, analysis_factory_mapping
from sflkit.analysis.predicate import Predicate
from sflkit.analysis.spectra import Spectrum
from sflkit.events.event_file import EventFile
from sflkit.features.value import Feature, FeatureValue, BinaryFeature, TertiaryFeature
from sflkit.features.vector import FeatureVector
from sflkit.model.model import Model
from sflkit.model.parallel import ParallelModel
from sflkit.model.scope import Scope
from sflkit.runners.run import TestResult


class FeatureBuilder(CombinationFactory):
    def __init__(self):
        super().__init__(list(map(lambda f: f(), analysis_factory_mapping.values())))
        self.analysis: dict[EventFile, list[AnalysisObject]] = dict()
        self.feature_vectors: Dict[EventFile, FeatureVector] = dict()
        self.all_features: Set[Feature] = set()
        self.name_map: Dict[EventFile, str] = dict()
        #: Feature per analysis object, keyed by identity. See :meth:`_feature`.
        self.features: Dict[int, Optional[Feature]] = dict()

    def __iter__(self) -> FeatureVector:
        yield from self.feature_vectors.values()

    def __next__(self) -> FeatureVector:
        yield from self.feature_vectors.values()

    def __len__(self):
        return len(self.feature_vectors)

    def run_ids(self):
        return set(self.feature_vectors.keys())

    def get_vector_by_id(self, run_id: int):
        return self.feature_vectors.get(run_id, None)

    def get_vectors(self) -> List[FeatureVector]:
        return list(self.feature_vectors.values())

    def get_all_features(self) -> List[Feature]:
        return sorted(list(self.all_features))

    def remove(self, run_id: int):
        if run_id in self.feature_vectors:
            del self.feature_vectors[run_id]

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        self.analysis[event_file] = super().get_analysis(event, event_file, scope)
        self.analysis[event_file].append(self)
        return self.analysis[event_file]

    #: Evaluation results, and the bare booleans some analyses return, mapped
    #: to feature values. A lookup replaces a `match` that ran once per
    #: analysis object per event.
    _EVALUATIONS = {
        EvaluationResult.TRUE: FeatureValue.TRUE,
        EvaluationResult.FALSE: FeatureValue.FALSE,
        True: FeatureValue.TRUE,
        False: FeatureValue.FALSE,
    }

    @staticmethod
    def map_evaluation(
        analysis: Spectrum, id_: EventFile, thread_id: Optional[int] = None
    ):
        return FeatureBuilder._EVALUATIONS.get(
            analysis.get_last_evaluation(id_, thread_id), FeatureValue.UNDEFINED
        )

    def prepare(self, event_file: EventFile, test_result: TestResult):
        self.analysis[event_file] = list()
        self.name_map[event_file] = os.path.basename(str(event_file.path))
        self.feature_vectors[event_file] = FeatureVector(event_file, test_result)

    def _feature(self, analysis: AnalysisObject) -> Optional[Feature]:
        """
        Return the feature standing for *analysis*, building it once.

        An analysis object's feature never changes, but this used to be rebuilt
        on every hit, and building it means formatting the object's name. On a
        realistic trace that was millions of throwaway ``Feature`` objects and
        name strings, which dominated the profile.

        The cache is keyed by object identity and holds the feature, which in
        turn references the analysis object, so an entry keeps its own key
        alive and an id can never be recycled underneath it.

        :param analysis: The analysis object.
        :returns: Its feature, or ``None`` if it does not stand for one.
        """
        key = id(analysis)
        try:
            return self.features[key]
        except KeyError:
            pass
        if isinstance(analysis, Predicate):
            feature = TertiaryFeature(str(analysis), analysis)
        elif isinstance(analysis, Spectrum):
            feature = BinaryFeature(str(analysis), analysis)
        else:
            feature = None
        self.features[key] = feature
        return feature

    # noinspection PyUnusedLocal
    def hit(self, id_: EventFile, event: Event, *args, **kwargs):
        vector = self.feature_vectors[id_]
        # FeatureVector.set_feature keeps the FIRST value a feature is given
        # for a run, so once this run has recorded a feature nothing can change
        # it. Checking that up front skips reading the evaluation, taking the
        # vector's lock and touching the feature set, which is the bulk of the
        # work on all but the first hit of each feature.
        recorded = vector.features
        thread_id = event.thread_id
        all_features = self.all_features
        for a in self.analysis[id_]:
            feature = self._feature(a)
            if feature is None or feature in recorded:
                continue
            vector.set_feature(feature, self.map_evaluation(a, id_, thread_id))
            all_features.add(feature)

    def merge(self, other: "FeatureBuilder") -> None:
        """
        Fold a builder that handled other runs into this one.

        Runs are independent, so what a worker built for its share is disjoint
        from every other worker's and merges by union. Subclasses that
        accumulate something across runs -- a call tree, say -- override this
        and merge that too, which is what lets
        :meth:`EventHandler.handle_files` spread any builder over processes
        without knowing what it builds.

        :param other: A builder that handled a different set of runs.
        """
        self.feature_vectors.update(other.feature_vectors)
        self.name_map.update(other.name_map)
        self.all_features.update(other.all_features)

    def copy(self):
        new_feature_builder = FeatureBuilder()
        new_feature_builder.all_features = set(self.all_features)
        new_feature_builder.feature_vectors = dict(self.feature_vectors)
        new_feature_builder.features = dict(self.features)
        return new_feature_builder

    def to_complete_vectors(self, features: Optional[List[Feature]] = None):
        features = features or self.get_all_features()
        complete_vectors = list()
        for vector in self:
            complete_vector = FeatureVector(vector.run_id, vector.result)
            for feature in features:
                complete_vector.set_feature(feature, vector.get_feature_value(feature))
            complete_vectors.append(complete_vector)
        return complete_vectors

    def to_df(
        self, label: Optional[str] = None, features: Optional[List[Feature]] = None
    ):
        """
        Build a dataframe of the collected vectors.

        pandas is imported here rather than at module scope because this is the
        only thing in the module that needs it, while the module itself is
        imported into every traced process: the collector runs inside the
        program under test, where pandas costs 70 MB of resident memory and
        280 ms of start-up per run and is never used.
        """
        import pandas as pd

        features = features or self.get_all_features()
        data = list()
        for vector in self:
            num_dict = vector.num_dict_vector(features)
            num_dict["test"] = self.name_map[vector.run_id]
            num_dict["failing"] = 1 if vector.result == TestResult.FAILING else 0
            if label:
                num_dict["label"] = label
            data.append(num_dict)
        return pd.DataFrame(data)


def handle_files_in_process(
    handler: "EventHandler", event_files: List[EventFile]
) -> FeatureBuilder:
    """
    Handle a share of the runs in one process and return what was built.

    At module level so it can be shipped to a worker.

    :param handler: The handler to work with, carrying the builder to use.
    :param event_files: The runs this worker is responsible for.
    :returns: The builder, holding this share's results.
    """
    for event_file in event_files:
        handler.handle(event_file)
    return handler.builder


class EventHandler:
    def __init__(
        self, thread_support: bool = False, workers: int = 4, processes: int = 1
    ):
        self.builder = FeatureBuilder()
        self.thread_support = thread_support
        if thread_support:
            self.model = ParallelModel(self.builder)
        else:
            self.model = Model(self.builder)
        self.workers = workers
        #: Worker processes to spread the runs over. Threads do not help:
        #: building is Python-level work and the GIL serializes it.
        self.processes = processes

    @staticmethod
    def map_result(failing: bool):
        match failing:
            case True:
                return TestResult.FAILING
            case False:
                return TestResult.PASSING
            case _:
                return TestResult.UNDEFINED

    def handle(self, event_file: EventFile):
        self.model.prepare(event_file)
        self.builder.prepare(event_file, self.map_result(event_file.failing))
        with event_file:
            for event in event_file.load():
                event.handle(
                    self.model,
                    event_file,
                )

    def handle_files(self, event_files: List[EventFile]):
        """
        Handle every run in *event_files*.

        :param event_files: The runs to handle.

        With ``processes`` above one the runs are dealt out to worker
        processes and each worker's builder is merged back. Callers on
        platforms that spawn workers (macOS, Windows) must guard their entry
        point with ``if __name__ == "__main__":``.

        A builder that prunes against the failing runs seen so far cannot be
        split this way unmodified: a worker only ever sees its own share, so
        the failing runs it prunes against are only the ones it was dealt.

        Call this on a handler that has not handled anything yet. Each worker
        starts from a copy of this handler, so state already accumulated here
        would be counted once per worker when the shares are merged back.
        """
        if self.processes > 1 and len(event_files) > 1:
            self._handle_files_with_processes(event_files)
        elif self.workers > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                list(executor.map(self.handle, event_files))
        else:
            for e in event_files:
                self.handle(e)

    def _handle_files_with_processes(self, event_files: List[EventFile]):
        """
        Deal the runs out to worker processes and merge what they build.

        :param event_files: The runs to handle.
        """
        chunks: List[List[EventFile]] = [[] for _ in range(self.processes)]
        # Round-robin: runs differ wildly in length, so dealing them out keeps
        # one worker from drawing all the long ones.
        for index, event_file in enumerate(event_files):
            chunks[index % self.processes].append(event_file)
        chunks = [chunk for chunk in chunks if chunk]
        with ProcessPoolExecutor(max_workers=len(chunks)) as executor:
            futures = [
                # `self`, not `self.copy()`: copy() rebuilds a plain
                # FeatureBuilder and would silently downgrade a subclass --
                # a tree builder would come back as a bare vector builder,
                # having quietly built no tree. Pickling carries the real
                # builder, its type and its configuration.
                executor.submit(handle_files_in_process, self, chunk)
                for chunk in chunks
            ]
            for future in futures:
                self.builder.merge(future.result())

    def copy(self):
        new_handler = EventHandler()
        new_handler.builder = self.builder.copy()
        new_handler.thread_support = self.thread_support
        if self.thread_support:
            new_handler.model = ParallelModel(new_handler.builder)
        else:
            new_handler.model = Model(new_handler.builder)
        new_handler.workers = self.workers
        return new_handler

    def to_df(self, label: str = None, features: List[Feature] = None):
        return self.builder.to_df(label=label, features=features)

    def get_vectors(self, features: List[Feature] = None) -> List[FeatureVector]:
        return self.builder.to_complete_vectors(features=features)
