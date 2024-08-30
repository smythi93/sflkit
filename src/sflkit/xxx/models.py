from typing import List, Optional, Set

from sflkit.analysis.spectra import Spectrum
from sflkit.model import Model, Scope, EventFile
from sflkitlib.events.event import TestLineEvent


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

    def __eq__(self, other):
        return (
            isinstance(other, WeightedAnalysis)
            and other.file == self.file
            and other.line == self.line
        )

    def set_weight(self, run_id: int):
        for analysis in self.analysis:
            analysis.adjust_weight(run_id, self.weight)


class TestSliceModel(Model):
    def __init__(self, factory):
        super().__init__(factory)
        self.slices = list()
        self.current_analysis = list()
        self.last_test_line_event: Optional[TestLineEvent] = None
        self.current_test_failing = False

    # noinspection PyUnresolvedReferences
    def handle_event(self, event, scope: Scope = None) -> Set["AnalysisObject"]:
        analysis = super().handle_event(event, scope)
        self.current_analysis.extend(analysis)
        return analysis

    def add(self, event):
        if event:
            self.slices.append(
                WeightedAnalysis(
                    event.file,
                    event.line,
                    self.current_analysis,
                )
            )
            self.current_analysis = list()

    def prepare(self, run_id: EventFile):
        super().prepare(run_id)
        self.last_test_line_event = None
        self.slices = list()
        self.current_analysis = list()
        self.current_test_failing = run_id.failing

    def follow_up(self, run_id):
        self.add(self.last_test_line_event)

    def handle_test_line_event(self, event):
        if self.current_test_failing:
            self.add(self.last_test_line_event)
            self.last_test_line_event = event


class TestLineModel(TestSliceModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.lines = 0

    def prepare(self, run_id):
        super().prepare(run_id)
        self.lines = 0

    def follow_up(self, run_id):
        super().follow_up(run_id)
        for line, slice_ in enumerate(self.slices, start=1):
            slice_.weight = line / max(self.lines, 1)
            slice_.set_weight(run_id)

    def handle_test_line_event(self, event):
        if self.current_test_failing:
            super().handle_test_line_event(event)
            self.lines += 1
