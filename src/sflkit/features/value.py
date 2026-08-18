import enum
import hashlib
from abc import abstractmethod, ABC
from typing import Optional

from sflkit.analysis.analysis_type import AnalysisObject


def feature_id(name: str) -> int:
    """
    Stable 64-bit identifier for a feature *name*.

    Deliberately not :func:`hash`: string hashing is randomized per process
    (``PYTHONHASHSEED``), so built-in hashes of the same feature differ between
    the worker that observed it and the parent that merges it. A digest of the
    name is identical everywhere, which is what lets observations recorded in
    separate processes be merged by id alone -- without shipping the feature's
    analysis object, and therefore the whole analysis graph hanging off it,
    across the process boundary.

    :param name: Canonical feature name, e.g. ``"Line(main.py:12)"``.
    :returns: The identifier.
    """
    return int.from_bytes(
        hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest(), "big"
    )


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
        self._id: Optional[int] = None
        # Features key the feature vector, so this is hashed once per analysis
        # object per event; the name never changes.
        self._hash = hash(name)

    @property
    def id(self) -> int:
        """
        The feature's stable, process-independent identifier.

        Computed from :attr:`name` on first access; see :func:`feature_id`.
        """
        if self._id is None:
            self._id = feature_id(self.name)
        return self._id

    @abstractmethod
    def default(self):
        raise NotImplementedError()

    def __hash__(self):
        return self._hash

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
