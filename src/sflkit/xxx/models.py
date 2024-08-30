from typing import List, Optional, Set, Dict

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

    def add(self, event, last: bool = False) -> Optional[WeightedAnalysis]:
        if self.last_test_event and (
            last
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
        self.add(None, last=True)

    def handle_test_line_event(self, event):
        if self.current_test_failing:
            self.add(event)


class TestLineModel(TestSliceModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.lines = 0

    def prepare(self, run_id):
        super().prepare(run_id)
        self.lines = 0

    def follow_up(self, run_id):
        super().follow_up(run_id)
        if run_id.failing:
            for line, slice_ in enumerate(self.slices, start=1):
                slice_.weight = line / max(self.lines, 1)
                slice_.set_weight(run_id)

    def handle_test_line_event(self, event):
        if self.current_test_failing:
            self.add(event)
            self.lines += 1


class TestDefUseModel(TestSliceModel):
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

    def add(self, event, last=False) -> Optional[WeightedAnalysis]:
        if event or last:
            slice_ = super().add(event, last=last)
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
        super().follow_up(run_id)
        if run_id.failing:
            distances: Dict[WeightedAnalysis, int] = dict()
            for distance, slice_ in enumerate(reversed(self.slices)):
                distances[slice_] = distance
            sorted_slices = sorted(self.slices, key=lambda s: distances[s])
            for slice_ in sorted_slices:
                if slice_ in self.use_def_slices:
                    if self.use_def_slices[slice_]:
                        for def_slice in self.use_def_slices[slice_]:
                            distances[def_slice] = min(
                                distances[def_slice], distances[slice_] + 1
                            )
            max_distance = max(max(distances.values()), 1) + 1
            for slice_ in distances:
                slice_.weight = 1 - distances[slice_] / max_distance
                slice_.set_weight(run_id)


class TestDefUsesModel(TestDefUseModel):
    pass


class TestAssertDefUseModel(TestDefUseModel):
    pass


class TestAssertDefUsesModel(TestDefUsesModel):
    pass
