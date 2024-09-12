import json
import os
from typing import Type, Optional, List, Callable, Set

from sflkit import Analyzer
from sflkit.analysis.analysis_type import AnalysisType, AnalysisObject
from sflkit.analysis.analyzer import load_analysis_json, deserialize
from sflkit.analysis.factory import AnalysisFactory
from sflkit.analysis.suggestion import Suggestion
from sflkit.weights.models import TestTimeModel
from sflkit.events.event_file import EventFile
from sflkit.model.model import MetaModel


class TimeAnalyzer(Analyzer):
    def __init__(
        self,
        model_class: Type[TestTimeModel],
        relevant_event_files: Optional[List[EventFile]] = None,
        irrelevant_event_files: Optional[List[EventFile]] = None,
        factory: Optional[AnalysisFactory] = None,
        meta_model: MetaModel = None,
    ):
        super().__init__(
            relevant_event_files=relevant_event_files,
            irrelevant_event_files=irrelevant_event_files,
            factory=factory,
            meta_model=meta_model,
            model_class=model_class,
        )

    def get_sorted_suggestions(
        self,
        base_dir,
        metric: Callable = None,
        type_: AnalysisType = None,
        use_weight: bool = False,
    ) -> List[Suggestion]:
        return super().get_sorted_suggestions(base_dir, metric, type_, use_weight=True)

    def get_sorted_suggestions_from_analysis(
        self,
        base_dir,
        analysis: Set[AnalysisObject],
        metric: Callable = None,
        use_weight: bool = False,
    ) -> List[Suggestion]:
        return super().get_sorted_suggestions_from_analysis(
            base_dir, analysis, metric, use_weight=True
        )

    @staticmethod
    def load_with_dependencies(path: os.PathLike, model_class: Type[TestTimeModel]):
        return TimeAnalyzer(model_class, meta_model=MetaModel(load_analysis_json(path)))

    @staticmethod
    def loads_with_dependencies(data: str, model_class: Type[TestTimeModel]):
        return TimeAnalyzer(
            model_class, meta_model=MetaModel(set(map(deserialize, json.loads(data))))
        )
