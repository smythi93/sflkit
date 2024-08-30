from typing import Type, Optional, List, Callable, Set

from sflkit import Analyzer
from sflkit.analysis.analysis_type import AnalysisType, AnalysisObject
from sflkit.analysis.factory import AnalysisFactory
from sflkit.analysis.suggestion import Suggestion
from sflkit.model import EventFile
from sflkit.xxx.models import TestSliceModel


class SliceAnalyzer(Analyzer):
    def __init__(
        self,
        model_class: Type[TestSliceModel],
        relevant_event_files: Optional[List[EventFile]] = None,
        irrelevant_event_files: Optional[List[EventFile]] = None,
        factory: Optional[AnalysisFactory] = None,
    ):
        super().__init__(
            relevant_event_files=relevant_event_files,
            irrelevant_event_files=irrelevant_event_files,
            factory=factory,
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
