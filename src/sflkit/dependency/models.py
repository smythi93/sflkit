from typing import List, Optional, Set, Dict, Tuple

from sflkit.analysis.spectra import Spectrum
from sflkit.events.event_file import EventFile
from sflkit.model.model import Model
from sflkit.model.scope import Scope
from sflkitlib.events.event import TestDefEvent, TestUseEvent, Event


class WeightedAnalyses:
    def __init__(
        self,
        file: str,
        line: int,
        analyses: Optional[List[Spectrum]] = None,
        weight: float = 0,
    ):
        self.file = file
        self.line = line
        self.analyses = analyses or list()
        self.weight = weight

    def __hash__(self):
        return hash((self.file, self.line))

    def __repr__(self):
        return f"{self.file}:{self.line}"

    def set_weight(self, event_file: EventFile):
        for analysis in self.analyses:
            analysis.adjust_weight(event_file, self.weight)


class TestDependencyModel(Model):
    def __init__(self, factory):
        super().__init__(factory)
        self.parts = list()
        self.current_analysis = list()
        self.last_test_event: Optional[Event] = None
        self.current_test_failing = False

    # noinspection PyUnresolvedReferences
    def handle_event(self, event, scope: Scope = None) -> Set["AnalysisObject"]:
        analysis = super().handle_event(event, scope)
        self.current_analysis.extend(analysis)
        return analysis

    def add(self, event, force: bool = False) -> Optional[WeightedAnalyses]:
        if self.last_test_event and (
            force
            or (
                event
                and (
                    self.last_test_event.line != event.line
                    or self.last_test_event.file != event.file
                )
            )
        ):
            weighted_analyses = WeightedAnalyses(
                self.last_test_event.file,
                self.last_test_event.line,
                self.current_analysis,
            )
            self.parts.append(weighted_analyses)
            self.current_analysis = list()
            self.last_test_event = event
            return weighted_analyses
        if event:
            self.last_test_event = event

    def prepare(self, event_file: EventFile):
        super().prepare(event_file)
        self.last_test_event = None
        self.parts = list()
        self.current_analysis = list()
        self.current_test_failing = event_file.failing

    def follow_up(self, event_file):
        self.add(None, force=True)

    def handle_test_line_event(self, event):
        if self.current_test_failing:
            self.add(event)

    def finalize(
        self, passed: Optional[List[EventFile]], failed: Optional[List[EventFile]]
    ):
        for p in self.get_analysis():
            if failed:
                for f in failed:
                    p.adjust_weight(f, 0)
            p.analyze(passed, failed)


class TestFunctionModel(TestDependencyModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.test_start_capture = False
        self.test_end_capture = False
        self.closest_analyses: Optional[WeightedAnalyses] = None
        self.before_analyses: Set[WeightedAnalyses] = set()
        self.actual_analyses: Set[WeightedAnalyses] = set()

    def prepare(self, event_file):
        super().prepare(event_file)
        self.before_analyses = set()
        self.actual_analyses = set()
        self.closest_analyses = None

    def handle_test_start_event(self, event):
        if self.current_test_failing:
            self.add(event)
            if not self.test_start_capture:
                self.before_analyses = set(self.parts)
                self.test_start_capture = True

    def handle_test_end_event(self, event):
        if self.current_test_failing:
            weighted_analyses = self.add(event, force=True)
            if weighted_analyses:
                self.closest_analyses = weighted_analyses
            self.actual_analyses = set(self.parts) - self.before_analyses
            self.test_end_capture = True

    def get_distances(self) -> Dict[WeightedAnalyses, int]:
        distances: Dict[WeightedAnalyses, int] = dict()
        if self.closest_analyses:
            closest = self.parts.index(self.closest_analyses)
            for distance, analyses in enumerate(reversed(self.parts[:closest])):
                distances[analyses] = distance
            for distance, analyses in enumerate(self.parts[closest:], start=1):
                distances[analyses] = distance
        else:
            for distance, analyses in enumerate(reversed(self.parts)):
                distances[analyses] = distance
        return distances

    def adjust_weights_for_tests(self, event_file):
        if event_file.failing:
            if self.test_end_capture:
                for analyses in self.parts:
                    if analyses in self.actual_analyses:
                        analyses.weight = 1
                    else:
                        analyses.weight = 0.5
            else:
                for analyses in self.parts:
                    if analyses in self.before_analyses:
                        analyses.weight = 0.5
                    else:
                        analyses.weight = 1

    def follow_up(self, event_file):
        super().follow_up(event_file)
        if event_file.failing:
            self.adjust_weights_for_tests(event_file)
            for analyses in self.parts:
                analyses.set_weight(event_file)


class TestLineModel(TestFunctionModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.lines = 0

    def prepare(self, event_file):
        super().prepare(event_file)
        self.lines = 0

    def follow_up(self, event_file):
        TestDependencyModel.follow_up(self, event_file)
        self.adjust_weights_for_tests(event_file)
        if event_file.failing:
            distances = self.get_distances()
            max_distance = max(max(distances.values()), 0) + 1
            for analyses in distances:
                analyses.weight *= 1 - distances[analyses] / max_distance
                analyses.set_weight(event_file)


class TestDefUseModel(TestFunctionModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.current_defs = list()
        self.current_uses = list()
        self.def_analyses: Dict[int, WeightedAnalyses] = dict()
        self.use_def_analyses: Dict[WeightedAnalyses, List[WeightedAnalyses]] = dict()

    def prepare(self, event_file):
        super().prepare(event_file)
        self.current_defs = list()
        self.current_uses = list()
        self.def_analyses = dict()
        self.use_def_analyses = dict()

    def add(self, event, force=False) -> Optional[WeightedAnalyses]:
        if event or force:
            analyses = super().add(event, force=force)
            if analyses:
                for def_ in self.current_defs:
                    self.def_analyses[(def_.var, def_.var_id)] = analyses
                def_uses = list()
                for use in self.current_uses:
                    if (use.var, use.var_id) in self.def_analyses:
                        def_uses.append(self.def_analyses[(use.var, use.var_id)])
                self.use_def_analyses[analyses] = def_uses
                self.current_defs = list()
                self.current_uses = list()

    def handle_test_def_event(self, event: TestDefEvent):
        if self.current_test_failing:
            self.add(event)
            self.current_defs.append(event)

    def handle_test_use_event(self, event: TestUseEvent):
        if self.current_test_failing:
            self.add(event)
            self.current_uses.append(event)

    def follow_up(self, event_file):
        TestDependencyModel.follow_up(self, event_file)
        self.adjust_weights_for_tests(event_file)
        if event_file.failing:
            distances = self.get_distances()
            sorted_analyses = sorted(self.parts, key=lambda s: distances[s])
            for analyses in sorted_analyses:
                if analyses in self.use_def_analyses:
                    if self.use_def_analyses[analyses]:
                        for def_analyses in self.use_def_analyses[analyses]:
                            distances[def_analyses] = min(
                                distances[def_analyses], distances[analyses] + 1
                            )
            max_distance = max(max(distances.values()), 0) + 1
            for analyses in distances:
                analyses.weight *= 1 - distances[analyses] / max_distance
                analyses.set_weight(event_file)


class TestDefUsesModel(TestDefUseModel):
    def add(self, event, force=False) -> Optional[WeightedAnalyses]:
        if event or force:
            analyses = TestFunctionModel.add(self, event, force=force)
            if analyses:
                for def_ in self.current_defs:
                    self.def_analyses[(def_.var, def_.var_id)] = analyses
                def_uses = list()
                for use in self.current_uses:
                    if (use.var, use.var_id) in self.def_analyses:
                        def_uses.append(self.def_analyses[(use.var, use.var_id)])
                self.use_def_analyses[analyses] = def_uses
                for use in self.current_uses:
                    if (use.var, use.var_id) in self.def_analyses:
                        self.def_analyses[(use.var, use.var_id)] = analyses
                self.current_defs = list()
                self.current_uses = list()


class TestAssertDefUseModel(TestDefUseModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.asserts: Set[Tuple[str, int]] = set()

    def prepare(self, event_file):
        super().prepare(event_file)
        self.asserts = set()

    def handle_test_assert_event(self, event):
        if self.current_test_failing:
            self.add(event)
            self.asserts.add((event.file, event.line))

    def follow_up(self, event_file):
        TestDependencyModel.follow_up(self, event_file)
        self.adjust_weights_for_tests(event_file)
        if event_file.failing:
            distances = self.get_distances()
            sorted_analyses = sorted(self.parts, key=lambda s: distances[s])
            assert_analyses = set()
            for analyses in sorted_analyses:
                if (
                    distances[analyses] > 0
                    and (analyses.file, analyses.line) in self.asserts
                ):
                    distances[analyses] += 1
                    assert_analyses.add(analyses)
                if analyses in self.use_def_analyses:
                    if self.use_def_analyses[analyses]:
                        for def_analyses in self.use_def_analyses[analyses]:
                            distances[def_analyses] = min(
                                distances[def_analyses], distances[analyses] + 1
                            )
                            if analyses in assert_analyses:
                                distances[def_analyses] += 1
                                assert_analyses.add(def_analyses)
            max_distance = max(max(distances.values()), 0) + 1
            for analyses in distances:
                analyses.weight *= 1 - distances[analyses] / max_distance
                analyses.set_weight(event_file)


class TestAssertDefUsesModel(TestAssertDefUseModel):
    def add(self, event, force=False) -> Optional[WeightedAnalyses]:
        TestDefUsesModel.add(self, event, force=force)
