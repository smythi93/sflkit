import os.path
from typing import List, Dict, Set, Optional

import pandas as pd
from sflkitlib.events.event import Event

from sflkit import Predicate
from sflkit.analysis.analysis_type import AnalysisObject, EvaluationResult
from sflkit.analysis.factory import CombinationFactory, analysis_factory_mapping
from sflkit.analysis.spectra import Spectrum
from sflkit.features.value import Feature, FeatureValue, BinaryFeature, TertiaryFeature
from sflkit.features.vector import FeatureVector
from sflkit.model import Model, EventFile, Scope
from sflkit.runners.run import TestResult


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
        self.feature_vectors: Dict[int, FeatureVector] = dict()
        self.all_features: Set[Feature] = set()
        self.name_map: Dict[int, str] = dict()

    def get_analysis(self, event, scope: Scope = None) -> List[AnalysisObject]:
        self.analysis = super().get_analysis(event, scope)
        self.analysis.append(self)
        return self.analysis

    @staticmethod
    def map_evaluation(analysis: Spectrum, id_: int):
        match analysis.get_last_evaluation(id_):
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
        self.name_map[event_file.run_id] = os.path.basename(str(event_file.path))
        self.feature_vectors[event_file.run_id] = FeatureVector(
            event_file.run_id, test_result
        )

    # noinspection PyUnusedLocal
    def hit(self, id_, *args, **kwargs):
        event: Event
        for a in self.analysis:
            if isinstance(a, Spectrum):
                feature = BinaryFeature(str(a), a)
                self.feature_vectors[id_].set_feature(
                    feature, self.map_evaluation(a, id_)
                )
                self.all_features.add(feature)
            elif isinstance(a, Predicate):
                feature = TertiaryFeature(str(a), a)
                self.feature_vectors[id_].set_feature(
                    feature, self.map_evaluation(a, id_)
                )
                self.all_features.add(feature)

    def copy(self):
        new_feature_builder = FeatureBuilder()
        new_feature_builder.all_features = set(self.all_features)
        new_feature_builder.feature_vectors = dict(self.feature_vectors)
        return new_feature_builder

    def to_df(self, label: Optional[str] = None):
        features = self.get_all_features()
        data = list()
        for vector in self:
            num_dict = vector.num_dict_vector(features)
            num_dict["test"] = self.name_map[vector.run_id]
            num_dict["failing"] = 1 if vector.result == TestResult.FAILING else 0
            if label:
                num_dict["label"] = label
            data.append(vector.num_dict_vector(features))
        return pd.DataFrame(data)


class EventHandler:
    def __init__(self):
        self.builder = FeatureBuilder()
        self.model = Model(self.builder)

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
        self.model.prepare(event_file.run_id)
        self.builder.prepare(event_file, self.map_result(event_file.failing))
        with event_file:
            for event in event_file.load():
                event.handle(self.model)

    def handle_files(self, event_files: List[EventFile]):
        for e in event_files:
            self.handle(e)

    def copy(self):
        new_handler = EventHandler()
        new_handler.feature_builder = self.builder.copy()
        new_handler.model = Model(new_handler.feature_builder)
        return new_handler

    def to_df(self):
        return self.builder.to_df()
