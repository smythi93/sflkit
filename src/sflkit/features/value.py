import enum
from abc import abstractmethod, ABC

from sflkit.analysis.analysis_type import AnalysisObject


class FeatureValue(enum.Enum):
    TRUE = 1
    FALSE = 0
    UNDEFINED = -1

    def __repr__(self):
        return self.name

    def __or__(self, other):
        if isinstance(other, FeatureValue):
            if other == FeatureValue.TRUE or self == FeatureValue.UNDEFINED:
                return other
            else:
                return self
        elif isinstance(other, bool):
            if other:
                return FeatureValue.TRUE
            elif self == FeatureValue.UNDEFINED:
                return FeatureValue.FALSE
            else:
                return self
        else:
            return self

    def __invert__(self):
        if self == FeatureValue.UNDEFINED:
            return FeatureValue.UNDEFINED
        elif self == FeatureValue.TRUE:
            return FeatureValue.FALSE
        else:
            return FeatureValue.TRUE

    def __neg__(self):
        if self == FeatureValue.UNDEFINED:
            return FeatureValue.UNDEFINED
        elif self == FeatureValue.TRUE:
            return FeatureValue.FALSE
        else:
            return FeatureValue.TRUE


class Feature(ABC):
    def __init__(self, name: str, analysis: AnalysisObject):
        self.name = name
        self.analysis = analysis

    @abstractmethod
    def default(self):
        raise NotImplementedError()

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return hasattr(other, "name") and self.name == other.name

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()

    def __lt__(self, other):
        if hasattr(other, "name"):
            return self.name < other.name
        else:
            raise TypeError(
                f"'<' not supported between instances of '{type(self)}' and '{type(other)}'"
            )

    def __gt__(self, other):
        if hasattr(other, "name"):
            return self.name > other.name
        else:
            raise TypeError(
                f"'>' not supported between instances of '{type(self)}' and '{type(other)}'"
            )


class BinaryFeature(Feature):
    def default(self):
        return FeatureValue.FALSE


class TertiaryFeature(Feature):
    def default(self):
        return FeatureValue.UNDEFINED
