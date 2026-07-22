import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Callable, Set, Dict, Optional, Any, Type

from sflkit.analysis.analysis_type import AnalysisType, AnalysisObject
from sflkit.analysis.factory import AnalysisFactory
from sflkit.analysis.predicate import (
    Branch,
    ScalarPair,
    VariablePredicate,
    NonePredicate,
    ReturnPredicate,
    EmptyStringPredicate,
    EmptyBytesPredicate,
    IsAsciiPredicate,
    ContainsDigitPredicate,
    ContainsSpecialPredicate,
    Condition,
    FunctionErrorPredicate,
)
from sflkit.analysis.spectra import Line, Function, DefUse, Loop, Length
from sflkit.analysis.suggestion import Suggestion
from sflkit.events.event_file import EventFile
from sflkit.model.model import Model, MetaModel
from sflkit.model.parallel import ParallelModel


class AnalysisEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, AnalysisObject):
            return o.serialize()
        else:
            super().default(o)


class Analyzer:
    def __init__(
        self,
        relevant_event_files: Optional[List[EventFile]] = None,
        irrelevant_event_files: Optional[List[EventFile]] = None,
        factory: Optional[AnalysisFactory] = None,
        meta_model: Optional[MetaModel] = None,
        model_class: Type[Model] = None,
        parallel: bool = False,
        workers: int = 4,
    ):
        if (
            relevant_event_files is None
            or irrelevant_event_files is None
            or factory is None
        ):
            if meta_model is None:
                raise ValueError("meta_model must be provided")
            self.meta = True
        else:
            self.meta = False
        self.relevant_event_files = relevant_event_files
        self.irrelevant_event_files = irrelevant_event_files
        if self.meta:
            self.model = meta_model
        else:
            if model_class is None:
                if parallel:
                    model_class = ParallelModel
                else:
                    model_class = Model
            self.model = model_class(factory)
        self.workers = workers
        self.paths: Dict[int, os.PathLike] = dict()
        self.max_suspiciousness = 0
        self.min_suspiciousness = 0
        self.mean_suspiciousness = 0
        self.median_suspiciousness = 0

    def _analyze(self, event_file):
        if self.meta:
            raise NotImplementedError("Not implemented for meta/loaded analyzer")
        self.model.prepare(event_file)
        with event_file:
            for event in event_file.load():
                event.handle(self.model, event_file)
        self.model.follow_up(event_file)

    def _finalize(self):
        if self.meta:
            raise NotImplementedError("Not implemented for meta/loaded analyzer")
        self.model.finalize(self.irrelevant_event_files, self.relevant_event_files)

    def analyze(self):
        if self.meta:
            raise NotImplementedError("Not implemented for meta/loaded analyzer")
        if self.workers > 1:
            event_files = self.relevant_event_files + self.irrelevant_event_files
            for event_file in event_files:
                self.paths[event_file.run_id] = event_file.path
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                list(executor.map(self._analyze, event_files))
        else:
            for event_file in self.relevant_event_files + self.irrelevant_event_files:
                self.paths[event_file.run_id] = event_file.path
                self._analyze(event_file)
        self._finalize()

    def dump(self, path: os.PathLike, indent: Optional[int] = None):
        with open(path, "w") as f:
            json.dump(self.get_analysis(), f, cls=AnalysisEncoder, indent=indent)

    def dumps(self, indent: Optional[int] = None):
        return json.dumps(self.get_analysis(), cls=AnalysisEncoder, indent=indent)

    @staticmethod
    def load(path: os.PathLike):
        return Analyzer(meta_model=MetaModel(load_analysis_json(path)))

    @staticmethod
    def loads(data: str):
        return Analyzer(meta_model=MetaModel(set(map(deserialize, json.loads(data)))))

    def get_analysis(self) -> Set[AnalysisObject]:
        return list(self.model.get_analysis())

    def get_analysis_by_type(self, type_: AnalysisType) -> Set[AnalysisObject]:
        return list(
            filter(lambda p: p.analysis_type() == type_, self.model.get_analysis())
        )

    def get_sorted_suggestions(
        self,
        base_dir,
        metric: Callable = None,
        type_: AnalysisType = None,
        use_weight: bool = False,
    ) -> List[Suggestion]:
        if type_:
            objects = self.get_analysis_by_type(type_)
        else:
            objects = self.get_analysis()
        return self.get_sorted_suggestions_from_analysis(
            base_dir, objects, metric, use_weight=use_weight
        )

    def get_sorted_suggestions_from_analysis(
        self,
        base_dir,
        analysis: Set[AnalysisObject],
        metric: Callable = None,
        use_weight: bool = False,
    ) -> List[Suggestion]:
        suggestions = dict()
        suspiciousness = list()
        for suggestion in map(
            lambda p: p.get_suggestion(
                metric=metric, base_dir=base_dir, use_weight=use_weight
            ),
            analysis,
        ):
            suspiciousness.append(suggestion.suspiciousness)
            if suggestion.suspiciousness not in suggestions:
                suggestions[suggestion.suspiciousness] = set(suggestion.lines)
            else:
                suggestions[suggestion.suspiciousness] |= set(suggestion.lines)

        if suspiciousness:
            self.max_suspiciousness = max(suspiciousness)
            self.min_suspiciousness = min(suspiciousness)
            self.mean_suspiciousness = sum(suspiciousness) / len(suspiciousness)
            self.median_suspiciousness = sorted(suspiciousness)[
                len(suspiciousness) // 2
            ]

        return sorted(
            [
                Suggestion(list(lines), suspiciousness)
                for suspiciousness, lines in suggestions.items()
            ],
            reverse=True,
        )[:]

    def get_coverage_per_run(
        self, type_: AnalysisType = None
    ) -> Dict[EventFile, Set[AnalysisObject]]:
        if type_:
            objects = self.get_analysis_by_type(type_)
        else:
            objects = self.get_analysis()
        coverage = dict()
        for obj in objects:
            for event_file in obj.hits:
                if event_file not in coverage:
                    coverage[event_file] = {obj}
                else:
                    coverage[event_file].add(obj)
        return coverage

    def get_coverage(self, type_: AnalysisType = None) -> Set[AnalysisObject]:
        coverage = self.get_coverage_per_run(type_)
        return set.union(*coverage.values())


def deserialize(analysis_object: dict) -> AnalysisObject:
    analysis_type = AnalysisType(analysis_object["type"])
    if analysis_type == AnalysisType.LINE:
        return Line.deserialize(analysis_object)
    elif analysis_type == AnalysisType.FUNCTION:
        return Function.deserialize(analysis_object)
    elif analysis_type == AnalysisType.DEF_USE:
        return DefUse.deserialize(analysis_object)
    elif analysis_type == AnalysisType.LOOP:
        return Loop.deserialize(analysis_object)
    elif analysis_type == AnalysisType.LENGTH:
        return Length.deserialize(analysis_object)
    elif analysis_type == AnalysisType.BRANCH:
        return Branch.deserialize(analysis_object)
    elif analysis_type == AnalysisType.SCALAR_PAIR:
        return ScalarPair.deserialize(analysis_object)
    elif analysis_type == AnalysisType.VARIABLE:
        return VariablePredicate.deserialize(analysis_object)
    elif analysis_type == AnalysisType.RETURN:
        return ReturnPredicate.deserialize(analysis_object)
    elif analysis_type == AnalysisType.NONE:
        return NonePredicate.deserialize(analysis_object)
    elif analysis_type == AnalysisType.EMPTY_STRING:
        return EmptyStringPredicate.deserialize(analysis_object)
    elif analysis_type == AnalysisType.EMPTY_BYTES:
        return EmptyBytesPredicate.deserialize(analysis_object)
    elif analysis_type == AnalysisType.ASCII_STRING:
        return IsAsciiPredicate.deserialize(analysis_object)
    elif analysis_type == AnalysisType.DIGIT_STRING:
        return ContainsDigitPredicate.deserialize(analysis_object)
    elif analysis_type == AnalysisType.SPECIAL_STRING:
        return ContainsSpecialPredicate.deserialize(analysis_object)
    elif analysis_type == AnalysisType.CONDITION:
        return Condition.deserialize(analysis_object)
    elif analysis_type == AnalysisType.FUNCTION_ERROR:
        return FunctionErrorPredicate.deserialize(analysis_object)
    else:
        raise ValueError(f"Unknown analysis type {analysis_type}")


def load_analysis_json(path):
    with open(path, "r") as f:
        data = json.load(f)
    return set(map(deserialize, data))
