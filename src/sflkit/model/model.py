from concurrent.futures import ThreadPoolExecutor
from typing import Set, List, Optional

from sflkit.analysis.analysis_type import AnalysisObject
from sflkit.events.event_file import EventFile
from sflkit.model.scope import Scope
from sflkitlib.events.event import (
    Event,
    LineEvent,
    BranchEvent,
    DefEvent,
    UseEvent,
    FunctionEnterEvent,
    FunctionExitEvent,
    FunctionErrorEvent,
    ConditionEvent,
    LoopBeginEvent,
    LoopHitEvent,
    LoopEndEvent,
    LenEvent,
    TestStartEvent,
    TestEndEvent,
    TestLineEvent,
    TestDefEvent,
    TestUseEvent,
    TestAssertEvent,
)


class MetaModel:
    # noinspection PyUnresolvedReferences
    def __init__(self, analysis_objects: Set[AnalysisObject] = None):
        self.analysis_objects = analysis_objects or set()

    # noinspection PyUnresolvedReferences
    def get_analysis(self) -> Set[AnalysisObject]:
        return self.analysis_objects


class Model:
    def __init__(self, factory, workers: int = 4):
        self.factory = factory
        self.variables: dict[EventFile, Scope] = dict()
        self.returns: dict[EventFile, Scope] = dict()
        self.workers: int = max(workers, 1)

    def prepare(self, event_file: EventFile):
        self.factory.reset(event_file)
        self.variables[event_file] = Scope()
        self.returns[event_file] = Scope()

    def follow_up(self, event_file):
        pass

    # noinspection PyUnresolvedReferences
    def handle_event(
        self,
        event: Event,
        event_file: EventFile,
        scope: Scope = None,
    ) -> Set[AnalysisObject]:
        analysis = self.factory.handle(event, event_file, scope=scope)
        for a in analysis:
            a.hit(event_file, event, scope=scope)
        return set(analysis)

    def handle_line_event(self, event: LineEvent, event_file: EventFile):
        self.handle_event(event, event_file)

    def handle_branch_event(self, event: BranchEvent, event_file: EventFile):
        self.handle_event(event, event_file)

    def handle_function_enter_event(
        self, event: FunctionEnterEvent, event_file: EventFile
    ):
        self.enter_scope(event_file)
        self.handle_event(event, event_file)

    def handle_function_exit_event(
        self, event: FunctionExitEvent, event_file: EventFile
    ):
        self.returns[event_file].add(event.function, event.return_value, event.type_)
        self.handle_event(event, event_file, self.returns[event_file])
        self.exit_scope(event_file)

    def handle_function_error_event(
        self, event: FunctionErrorEvent, event_file: EventFile
    ):
        self.handle_event(event, event_file)
        self.exit_scope(event_file)

    def handle_def_event(self, event: DefEvent, event_file: EventFile):
        self.variables[event_file].add(event.var, event.value, event.type_)
        self.handle_event(event, event_file, self.variables[event_file])

    def handle_use_event(self, event: UseEvent, event_file: EventFile):
        self.handle_event(event, event_file, self.variables[event_file])

    def handle_condition_event(self, event: ConditionEvent, event_file: EventFile):
        self.handle_event(event, event_file)

    def handle_loop_begin_event(self, event: LoopBeginEvent, event_file: EventFile):
        self.handle_event(event, event_file)

    def handle_loop_hit_event(self, event: LoopHitEvent, event_file: EventFile):
        self.handle_event(event, event_file)

    def handle_loop_end_event(self, event: LoopEndEvent, event_file: EventFile):
        self.handle_event(event, event_file)

    def handle_len_event(self, event: LenEvent, event_file: EventFile):
        self.handle_event(event, event_file)

    def handle_test_start_event(self, event: TestStartEvent, event_file: EventFile):
        pass

    def handle_test_end_event(self, event: TestEndEvent, event_file: EventFile):
        pass

    def handle_test_line_event(self, event: TestLineEvent, event_file: EventFile):
        pass

    def handle_test_def_event(self, event: TestDefEvent, event_file: EventFile):
        pass

    def handle_test_use_event(self, event: TestUseEvent, event_file: EventFile):
        pass

    def handle_test_assert_event(self, event: TestAssertEvent, event_file: EventFile):
        pass

    def enter_scope(self, event_file: EventFile):
        self.variables[event_file] = self.variables[event_file].enter()

    def exit_scope(self, event_file: EventFile):
        self.variables[event_file] = self.variables[event_file].exit()

    # noinspection PyUnresolvedReferences
    def get_analysis(self) -> Set[AnalysisObject]:
        return self.factory.get_all()

    def finalize(
        self, passed: Optional[List[EventFile]], failed: Optional[List[EventFile]]
    ):
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = []
            for p in self.get_analysis():
                futures.append(executor.submit(p.analyze, passed, failed))
            for future in futures:
                future.result()
