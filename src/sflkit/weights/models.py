from typing import List, Optional, Set, Dict, Tuple

from sflkitlib.events.event import (
    TestDefEvent,
    TestUseEvent,
    Event,
    TestLineEvent,
    TestStartEvent,
)

from sflkit.analysis.spectra import Spectrum
from sflkit.events.event_file import EventFile
from sflkit.model.parallel import ParallelModel
from sflkit.model.scope import Scope


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


class TestTimeModel(ParallelModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.parts: dict[EventFile, list] = dict()
        self.current_analysis: dict[EventFile, list] = dict()
        self.last_test_event: dict[EventFile, Optional[Event]] = dict()
        self.current_test_failing: dict[EventFile, bool] = dict()

    # noinspection PyUnresolvedReferences
    def handle_event(
        self, event, event_file: EventFile, scope: Scope = None
    ) -> Set["AnalysisObject"]:
        analysis = super().handle_event(event, event_file, scope)
        self.current_analysis[event_file].extend(analysis)
        return analysis

    def add(
        self, event, event_file: EventFile, force: bool = False
    ) -> Optional[WeightedAnalyses]:
        if self.last_test_event[event_file] and (
            force
            or (
                event
                and (
                    self.last_test_event[event_file].line != event.line
                    or self.last_test_event[event_file].file != event.file
                )
            )
        ):
            weighted_analyses = WeightedAnalyses(
                self.last_test_event[event_file].file,
                self.last_test_event[event_file].line,
                self.current_analysis[event_file],
            )
            self.parts[event_file].append(weighted_analyses)
            self.current_analysis[event_file] = list()
            self.last_test_event[event_file] = event
            return weighted_analyses
        if event:
            self.last_test_event[event_file] = event
        return None

    def prepare(self, event_file: EventFile):
        super().prepare(event_file)
        self.last_test_event[event_file] = None
        self.parts[event_file] = list()
        self.current_analysis[event_file] = list()
        self.current_test_failing[event_file] = event_file.failing

    def follow_up(self, event_file):
        self.add(None, event_file, force=True)

    def handle_test_line_event(self, event: TestLineEvent, event_file: EventFile):
        if self.current_test_failing:
            self.add(event, event_file)


class TestFunctionModel(TestTimeModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.test_start_capture: dict[EventFile, bool] = dict()
        self.test_end_capture: dict[EventFile, bool] = dict()
        self.closest_analyses: dict[EventFile, Optional[WeightedAnalyses]] = dict()
        self.before_analyses: dict[EventFile, Set[WeightedAnalyses]] = dict()
        self.actual_analyses: dict[EventFile, Set[WeightedAnalyses]] = dict()

    def prepare(self, event_file):
        super().prepare(event_file)
        self.test_start_capture[event_file] = False
        self.test_end_capture[event_file] = False
        self.before_analyses[event_file] = set()
        self.actual_analyses[event_file] = set()
        self.closest_analyses[event_file] = None

    def handle_test_start_event(self, event: TestStartEvent, event_file: EventFile):
        if self.current_test_failing[event_file]:
            self.add(event, event_file)
            if not self.test_start_capture[event_file]:
                self.before_analyses[event_file] = set(self.parts[event_file])
                self.test_start_capture[event_file] = True

    def handle_test_end_event(self, event: Event, event_file: EventFile):
        if self.current_test_failing[event_file]:
            weighted_analyses = self.add(event, event_file, force=True)
            if weighted_analyses:
                self.closest_analyses[event_file] = weighted_analyses
            self.actual_analyses[event_file] = (
                set(self.parts[event_file]) - self.before_analyses[event_file]
            )
            self.test_end_capture[event_file] = True

    def get_distances(self, event_file: EventFile) -> Dict[WeightedAnalyses, int]:
        distances: Dict[WeightedAnalyses, int] = dict()
        if self.closest_analyses[event_file]:
            closest = self.parts[event_file].index(self.closest_analyses[event_file])
            for distance, analyses in enumerate(
                reversed(self.parts[event_file][:closest])
            ):
                distances[analyses] = distance
            for distance, analyses in enumerate(
                self.parts[event_file][closest:], start=1
            ):
                distances[analyses] = distance
        else:
            for distance, analyses in enumerate(reversed(self.parts[event_file])):
                distances[analyses] = distance
        return distances

    def adjust_weights_for_tests(self, event_file):
        if event_file.failing:
            if self.test_end_capture[event_file]:
                for analyses in self.parts[event_file]:
                    if analyses in self.actual_analyses[event_file]:
                        analyses.weight = 1
                    else:
                        analyses.weight = 0.5
            else:
                for analyses in self.parts[event_file]:
                    if analyses in self.before_analyses[event_file]:
                        analyses.weight = 0.5
                    else:
                        analyses.weight = 1

    def follow_up(self, event_file):
        super().follow_up(event_file)
        if event_file.failing:
            self.adjust_weights_for_tests(event_file)
            for analyses in self.parts[event_file]:
                analyses.set_weight(event_file)


class TestLineModel(TestFunctionModel):
    def __init__(self, factory):
        super().__init__(factory)

    def follow_up(self, event_file):
        TestTimeModel.follow_up(self, event_file)
        self.adjust_weights_for_tests(event_file)
        if event_file.failing:
            distances = self.get_distances(event_file)
            max_distance = max(max(distances.values()), 0) + 1
            for analyses in distances:
                analyses.weight *= 1 - distances[analyses] / max_distance
                analyses.set_weight(event_file)


class TestDefUseModel(TestFunctionModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.current_defs: dict[EventFile, list] = dict()
        self.current_uses: dict[EventFile, list] = dict()
        self.def_analyses: dict[EventFile, dict[int, WeightedAnalyses]] = dict()
        self.use_def_analyses: dict[
            EventFile, dict[WeightedAnalyses, List[WeightedAnalyses]]
        ] = dict()

    def prepare(self, event_file):
        super().prepare(event_file)
        self.current_defs[event_file] = list()
        self.current_uses[event_file] = list()
        self.def_analyses[event_file] = dict()
        self.use_def_analyses[event_file] = dict()

    def add(
        self, event: Event, event_file: EventFile, force=False
    ) -> Optional[WeightedAnalyses]:
        if event or force:
            analyses = super().add(event, event_file, force=force)
            if analyses:
                for def_ in self.current_defs[event_file]:
                    self.def_analyses[event_file][(def_.var, def_.var_id)] = analyses
                def_uses = list()
                for use in self.current_uses[event_file]:
                    if (use.var, use.var_id) in self.def_analyses[event_file]:
                        def_uses.append(
                            self.def_analyses[event_file][(use.var, use.var_id)]
                        )
                self.use_def_analyses[event_file][analyses] = def_uses
                self.current_defs[event_file] = list()
                self.current_uses[event_file] = list()

    def handle_test_def_event(self, event: TestDefEvent, event_file: EventFile):
        if self.current_test_failing[event_file]:
            self.add(event, event_file)
            self.current_defs[event_file].append(event)

    def handle_test_use_event(self, event: TestUseEvent, event_file: EventFile):
        if self.current_test_failing[event_file]:
            self.add(event, event_file)
            self.current_uses[event_file].append(event)

    def get_distances(self, event_file: EventFile) -> Dict[WeightedAnalyses, int]:
        distances = super().get_distances(event_file)
        sorted_analyses = sorted(self.parts[event_file], key=lambda s: distances[s])
        for analyses in sorted_analyses:
            if analyses in self.use_def_analyses[event_file]:
                if self.use_def_analyses[event_file][analyses]:
                    for def_analyses in self.use_def_analyses[event_file][analyses]:
                        distances[def_analyses] = min(
                            distances[def_analyses], distances[analyses] + 1
                        )
        return distances

    def follow_up(self, event_file):
        TestTimeModel.follow_up(self, event_file)
        self.adjust_weights_for_tests(event_file)
        if event_file.failing:
            distances = self.get_distances(event_file)
            max_distance = max(max(distances.values()), 0) + 1
            for analyses in distances:
                analyses.weight *= 1 - distances[analyses] / max_distance
                analyses.set_weight(event_file)


class TestDefUsesModel(TestDefUseModel):
    def add(
        self, event, event_file: EventFile, force=False
    ) -> Optional[WeightedAnalyses]:
        if event or force:
            analyses = TestFunctionModel.add(self, event, event_file, force=force)
            if analyses:
                for def_ in self.current_defs[event_file]:
                    self.def_analyses[event_file][(def_.var, def_.var_id)] = analyses
                def_uses = list()
                for use in self.current_uses[event_file]:
                    if (use.var, use.var_id) in self.def_analyses[event_file]:
                        def_uses.append(
                            self.def_analyses[event_file][(use.var, use.var_id)]
                        )
                self.use_def_analyses[event_file][analyses] = def_uses
                for use in self.current_uses[event_file]:
                    if (use.var, use.var_id) in self.def_analyses[event_file]:
                        self.def_analyses[event_file][(use.var, use.var_id)] = analyses
                self.current_defs[event_file] = list()
                self.current_uses[event_file] = list()


class TestAssertDefUseModel(TestDefUseModel):
    def __init__(self, factory):
        super().__init__(factory)
        self.asserts: dict[EventFile, Set[Tuple[str, int]]] = dict()

    def prepare(self, event_file):
        super().prepare(event_file)
        self.asserts[event_file] = set()

    def handle_test_assert_event(self, event: TestDefEvent, event_file: EventFile):
        if self.current_test_failing[event_file]:
            self.add(event, event_file)
            self.asserts[event_file].add((event.file, event.line))

    def get_distances(self, event_file: EventFile) -> Dict[WeightedAnalyses, int]:
        distances = super().get_distances(event_file)
        sorted_analyses = sorted(self.parts[event_file], key=lambda s: distances[s])
        assert_analyses = set()
        for analyses in sorted_analyses:
            if (
                distances[analyses] > 0
                and (analyses.file, analyses.line) in self.asserts[event_file]
            ):
                distances[analyses] += 1
                assert_analyses.add(analyses)
            if analyses in self.use_def_analyses[event_file]:
                if self.use_def_analyses[event_file][analyses]:
                    for def_analyses in self.use_def_analyses[event_file][analyses]:
                        distances[def_analyses] = min(
                            distances[def_analyses], distances[analyses] + 1
                        )
                        if analyses in assert_analyses:
                            distances[def_analyses] += 1
                            assert_analyses.add(def_analyses)
        return distances

    def follow_up(self, event_file):
        TestTimeModel.follow_up(self, event_file)
        self.adjust_weights_for_tests(event_file)
        if event_file.failing:
            distances = self.get_distances(event_file)
            max_distance = max(max(distances.values()), 0) + 1
            for analyses in distances:
                analyses.weight *= 1 - distances[analyses] / max_distance
                analyses.set_weight(event_file)


class TestAssertDefUsesModel(TestAssertDefUseModel):
    def add(
        self, event, event_file: EventFile, force=False
    ) -> Optional[WeightedAnalyses]:
        TestDefUsesModel.add(self, event, event_file, force=force)
