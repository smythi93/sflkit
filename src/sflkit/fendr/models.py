from typing import List, Optional, Set, Dict, Tuple

from sflkit.analysis.spectra import Spectrum
from sflkit.model import Model, Scope, EventFile
from sflkitlib.events.event import TestDefEvent, TestUseEvent, Event


class WeightedAnalysis:
    def __init__(
        self,
        file: str,
        line: int,
        analysis: Optional[List[Spectrum]] = None,
        weight: float = 0,
    ):
        self.file = file
        self.line = line
        self.analysis = analysis or list()
        self.weight = weight

    def __hash__(self):
        return hash((self.file, self.line))

    def __repr__(self):
        return f"{self.file}:{self.line}"

    def set_weight(self, run_id: int):
        for analysis in self.analysis:
            analysis.adjust_weight(run_id, self.weight)


class TestSliceModel(Model):
    def __init__(self, factory):
        super().__init__(factory)
        self.slices = list()
        self.current_analysis = list()
        self.last_test_event: Optional[Event] = None
        self.current_test_failing = False

    # noinspection PyUnresolvedReferences
    def handle_event(self, event, scope: Scope = None) -> Set["AnalysisObject"]:
        analysis = super().handle_event(event, scope)
        self.current_analysis.extend(analysis)
        return analysis

    def add(self, event, force: bool = False) -> Optional[WeightedAnalysis]:
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
            slice_ = WeightedAnalysis(
                self.last_test_event.file,
                self.last_test_event.line,
                self.current_analysis,
            )
            self.slices.append(slice_)
            self.current_analysis = list()
            self.last_test_event = event
            return slice_
        if event:
            self.last_test_event = event

    def prepare(self, run_id: EventFile):
        super().prepare(run_id)
        self.last_test_event = None
        self.slices = list()
        self.current_analysis = list()
        self.current_test_failing = run_id.failing

    def follow_up(self, run_id):
        self.add(None, force=True)

    def handle_test_line_event(self, event):
        if self.current_test_failing:
            self.add(event)


class TestFunctionModel(TestSliceModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.test_start_capture = False
        self.test_end_capture = False
        self.closest_slice: Optional[WeightedAnalysis] = None
        self.before_slices: Set[WeightedAnalysis] = set()
        self.actual_slices: Set[WeightedAnalysis] = set()

    def prepare(self, run_id):
        super().prepare(run_id)
        self.before_slices = set()
        self.actual_slices = set()
        self.closest_slice = None

    def handle_test_start_event(self, event):
        if self.current_test_failing:
            self.add(event)
            if not self.test_start_capture:
                self.before_slices = set(self.slices)
                self.test_start_capture = True

    def handle_test_end_event(self, event):
        if self.current_test_failing:
            slice_ = self.add(event, force=True)
            if slice_:
                self.closest_slice = slice_
            self.actual_slices = set(self.slices) - self.before_slices
            self.test_end_capture = True

    def get_distances(self) -> Dict[WeightedAnalysis, int]:
        distances: Dict[WeightedAnalysis, int] = dict()
        if self.closest_slice:
            closest = self.slices.index(self.closest_slice)
            for distance, slice_ in enumerate(reversed(self.slices[:closest])):
                distances[slice_] = distance
            for distance, slice_ in enumerate(self.slices[closest:], start=1):
                distances[slice_] = distance
        else:
            for distance, slice_ in enumerate(reversed(self.slices)):
                distances[slice_] = distance
        return distances

    def adjust_weights_for_tests(self, run_id):
        if run_id.failing:
            if self.test_end_capture:
                for slice_ in self.slices:
                    if slice_ in self.actual_slices:
                        slice_.weight = 1
                    else:
                        slice_.weight = 0.5
            else:
                for slice_ in self.slices:
                    if slice_ in self.before_slices:
                        slice_.weight = 0.5
                    else:
                        slice_.weight = 1

    def follow_up(self, run_id):
        super().follow_up(run_id)
        if run_id.failing:
            self.adjust_weights_for_tests(run_id)
            for slice_ in self.slices:
                slice_.set_weight(run_id)


class TestLineModel(TestFunctionModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.lines = 0

    def prepare(self, run_id):
        super().prepare(run_id)
        self.lines = 0

    def follow_up(self, run_id):
        TestSliceModel.follow_up(self, run_id)
        self.adjust_weights_for_tests(run_id)
        if run_id.failing:
            distances = self.get_distances()
            max_distance = max(max(distances.values()), 0) + 1
            for slice_ in distances:
                slice_.weight *= 1 - distances[slice_] / max_distance
                slice_.set_weight(run_id)


class TestDefUseModel(TestFunctionModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.current_defs = list()
        self.current_uses = list()
        self.def_slices: Dict[int, WeightedAnalysis] = dict()
        self.use_def_slices: Dict[WeightedAnalysis, List[WeightedAnalysis]] = dict()

    def prepare(self, run_id):
        super().prepare(run_id)
        self.current_defs = list()
        self.current_uses = list()
        self.def_slices = dict()
        self.use_def_slices = dict()

    def add(self, event, force=False) -> Optional[WeightedAnalysis]:
        if event or force:
            slice_ = super().add(event, force=force)
            if slice_:
                for def_ in self.current_defs:
                    self.def_slices[(def_.var, def_.var_id)] = slice_
                def_uses = list()
                for use in self.current_uses:
                    if (use.var, use.var_id) in self.def_slices:
                        def_uses.append(self.def_slices[(use.var, use.var_id)])
                self.use_def_slices[slice_] = def_uses
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

    def follow_up(self, run_id):
        TestSliceModel.follow_up(self, run_id)
        self.adjust_weights_for_tests(run_id)
        if run_id.failing:
            distances = self.get_distances()
            sorted_slices = sorted(self.slices, key=lambda s: distances[s])
            for slice_ in sorted_slices:
                if slice_ in self.use_def_slices:
                    if self.use_def_slices[slice_]:
                        for def_slice in self.use_def_slices[slice_]:
                            distances[def_slice] = min(
                                distances[def_slice], distances[slice_] + 1
                            )
            max_distance = max(max(distances.values()), 0) + 1
            for slice_ in distances:
                slice_.weight *= 1 - distances[slice_] / max_distance
                slice_.set_weight(run_id)


class TestDefUsesModel(TestDefUseModel):
    def add(self, event, force=False) -> Optional[WeightedAnalysis]:
        if event or force:
            slice_ = TestFunctionModel.add(self, event, force=force)
            if slice_:
                for def_ in self.current_defs:
                    self.def_slices[(def_.var, def_.var_id)] = slice_
                def_uses = list()
                for use in self.current_uses:
                    if (use.var, use.var_id) in self.def_slices:
                        def_uses.append(self.def_slices[(use.var, use.var_id)])
                self.use_def_slices[slice_] = def_uses
                for use in self.current_uses:
                    if (use.var, use.var_id) in self.def_slices:
                        self.def_slices[(use.var, use.var_id)] = slice_
                self.current_defs = list()
                self.current_uses = list()


class TestAssertDefUseModel(TestDefUseModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.asserts: Set[Tuple[str, int]] = set()

    def prepare(self, run_id):
        super().prepare(run_id)
        self.asserts = set()

    def handle_test_assert_event(self, event):
        if self.current_test_failing:
            self.add(event)
            self.asserts.add((event.file, event.line))

    def follow_up(self, run_id):
        TestSliceModel.follow_up(self, run_id)
        self.adjust_weights_for_tests(run_id)
        if run_id.failing:
            distances = self.get_distances()
            sorted_slices = sorted(self.slices, key=lambda s: distances[s])
            assert_slices = set()
            for slice_ in sorted_slices:
                if distances[slice_] > 0 and (slice_.file, slice_.line) in self.asserts:
                    distances[slice_] += 1
                    assert_slices.add(slice_)
                if slice_ in self.use_def_slices:
                    if self.use_def_slices[slice_]:
                        for def_slice in self.use_def_slices[slice_]:
                            distances[def_slice] = min(
                                distances[def_slice], distances[slice_] + 1
                            )
                            if slice_ in assert_slices:
                                distances[def_slice] += 1
                                assert_slices.add(def_slice)
            max_distance = max(max(distances.values()), 0) + 1
            for slice_ in distances:
                slice_.weight *= 1 - distances[slice_] / max_distance
                slice_.set_weight(run_id)


class TestAssertDefUsesModel(TestAssertDefUseModel):
    def add(self, event, force=False) -> Optional[WeightedAnalysis]:
        TestDefUsesModel.add(self, event, force=force)
