from threading import Lock
from typing import Dict, List, Tuple, Set

from sflkit.events.event_file import EventFile
from sflkit.features.value import Feature, FeatureValue
from sflkit.runners.run import TestResult


class FeatureVector:
    def __init__(
        self,
        run_id: EventFile,
        result: TestResult,
    ):
        self.run_id = run_id
        self.result = result
        self.features: Dict[Feature, FeatureValue] = dict()
        self._lock = Lock()

    def get_features_set(self) -> Set[Feature]:
        with self._lock:
            return set(self.features.keys())

    def get_feature_value(self, feature: Feature) -> FeatureValue:
        with self._lock:
            if feature in self.features:
                return self.features[feature]
            else:
                return feature.default()

    def set_feature(self, feature: Feature, value: FeatureValue):
        with self._lock:
            if feature not in self.features:
                self.features[feature] = value
            else:
                self.features[feature] = self.features[feature] or value

    def get_features(self) -> Dict[Feature, FeatureValue]:
        with self._lock:
            return dict(self.features)

    def vector(self, features: List[Feature]) -> List[FeatureValue]:
        return [self.get_feature_value(feature) for feature in features]

    def num_vector(self, features: List[Feature]) -> List[int]:
        return [value.value for value in self.vector(features)]

    def dict_vector(self, features: List[Feature]) -> Dict[Feature, FeatureValue]:
        return {feature: self.get_feature_value(feature) for feature in features}

    def num_dict_vector(self, features: List[Feature]) -> Dict[str, int]:
        return {
            feature.name: value.value
            for feature, value in self.dict_vector(features).items()
        }

    def tuple(self, features: List[Feature]) -> Tuple[Tuple[Feature, FeatureValue]]:
        return tuple((feature, self.get_feature_value(feature)) for feature in features)

    def __repr__(self):
        with self._lock:
            return f"{self.result.name}{self.features}"

    def __str__(self):
        with self._lock:
            return f"{self.result.name}{self.features}"

    def __eq__(self, other):
        if isinstance(other, FeatureVector) and self.result == other.result:
            with self._lock:
                self_keys = set(self.features.keys())
            with other._lock:
                other_keys = set(other.features.keys())
            for feature in self_keys.union(other_keys):
                if self.get_feature_value(feature) != other.get_feature_value(feature):
                    return False
            return True
        else:
            return False

    def difference(self, other, features: List[Feature]):
        if isinstance(other, FeatureVector):
            s = 0
            for feature in features:
                s += self.get_feature_value(feature) != other.get_feature_value(feature)
            return s
        else:
            return 0
