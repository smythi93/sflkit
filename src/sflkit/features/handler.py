import os.path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Set, Optional

import pandas as pd

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
from sflkitlib.events.event import Event


class FeatureBuilder(CombinationFactory):
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

    def __init__(self):
        super().__init__(list(map(lambda f: f(), analysis_factory_mapping.values())))
        self.analysis: List[AnalysisObject] = list()
        self.feature_vectors: Dict[EventFile, FeatureVector] = dict()
        self.all_features: Set[Feature] = set()
        self.name_map: Dict[EventFile, str] = dict()

    def get_analysis(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> List[AnalysisObject]:
        self.analysis = super().get_analysis(event, event_file, scope)
        self.analysis.append(self)
        return self.analysis

    @staticmethod
    def map_evaluation(analysis: Spectrum, id_: EventFile, thread_id: Optional[int] = None):
        match analysis.get_last_evaluation(id_, thread_id):
            case EvaluationResult.TRUE:
                return FeatureValue.TRUE
            case EvaluationResult.FALSE:
                return FeatureValue.FALSE
            case True:
                return FeatureValue.TRUE
            case False:
                return FeatureValue.FALSE
            case _:
                return FeatureValue.UNDEFINED

    def prepare(self, event_file: EventFile, test_result: TestResult):
        self.name_map[event_file] = os.path.basename(str(event_file.path))
        self.feature_vectors[event_file] = FeatureVector(event_file, test_result)

    # noinspection PyUnusedLocal
    def hit(self, id_: EventFile, event: Event, *args, **kwargs):
        for a in self.analysis:
            if isinstance(a, Predicate):
                feature = TertiaryFeature(str(a), a)
                self.feature_vectors[id_].set_feature(
                    feature, self.map_evaluation(a, id_, event.thread_id)
                )
                self.all_features.add(feature)
            elif isinstance(a, Spectrum):
                feature = BinaryFeature(str(a), a)
                self.feature_vectors[id_].set_feature(
                    feature, self.map_evaluation(a, id_, event.thread_id)
                )
                self.all_features.add(feature)

    def copy(self):
        new_feature_builder = FeatureBuilder()
        new_feature_builder.all_features = set(self.all_features)
        new_feature_builder.feature_vectors = dict(self.feature_vectors)
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


class EventHandler:
    def __init__(self, thread_support: bool = False, workers: int = 4):
        self.builder = FeatureBuilder()
        self.thread_support = thread_support
        if thread_support:
            self.model = ParallelModel(self.builder)
        else:
            self.model = Model(self.builder)
        self.workers = workers

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
        if self.workers > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                list(executor.map(self.handle, event_files))
        else:
            for e in event_files:
                self.handle(e)

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
