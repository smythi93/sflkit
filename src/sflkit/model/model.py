from typing import Set, List, Optional

from sflkit.analysis.analysis_type import AnalysisObject
from sflkit.events.event_file import EventFile
from sflkit.model.scope import Scope


class MetaModel:
    # noinspection PyUnresolvedReferences
    def __init__(self, analysis_objects: Set[AnalysisObject] = None):
        self.analysis_objects = analysis_objects or set()

    # noinspection PyUnresolvedReferences
    def get_analysis(self) -> Set[AnalysisObject]:
        return self.analysis_objects


class Model:
    def __init__(self, factory):
        self.factory = factory
        self.variables = Scope()
        self.returns = Scope()
        self.current_event_file = None

    def prepare(self, event_file):
        self.factory.reset()
        self.variables = Scope()
        self.returns = Scope()
        self.current_event_file = event_file

    def follow_up(self, event_file):
        pass

    # noinspection PyUnresolvedReferences
    def handle_event(self, event, scope: Scope = None) -> Set[AnalysisObject]:
        analysis = self.factory.handle(event, scope=scope)
        for a in analysis:
            a.hit(self.current_event_file, event, scope)
        return set(analysis)

    def handle_line_event(self, event):
        self.handle_event(event)

    def handle_branch_event(self, event):
        self.handle_event(event)

    def handle_function_enter_event(self, event):
        self.enter_scope()
        self.handle_event(event)

    def handle_function_exit_event(self, event):
        self.returns.add(event.function, event.return_value, event.type_)
        self.handle_event(event, self.returns)
        self.exit_scope()

    def handle_function_error_event(self, event):
        self.handle_event(event)
        self.exit_scope()

    def handle_def_event(self, event):
        self.variables.add(event.var, event.value, event.type_)
        self.handle_event(event, self.variables)

    def handle_use_event(self, event):
        self.handle_event(event, self.variables)

    def handle_condition_event(self, event):
        self.handle_event(event)

    def handle_loop_begin_event(self, event):
        self.handle_event(event)

    def handle_loop_hit_event(self, event):
        self.handle_event(event)

    def handle_loop_end_event(self, event):
        self.handle_event(event)

    def handle_len_event(self, event):
        self.handle_event(event)

    def handle_test_start_event(self, event):
        pass

    def handle_test_end_event(self, event):
        pass

    def handle_test_line_event(self, event):
        pass

    def handle_test_def_event(self, event):
        pass

    def handle_test_use_event(self, event):
        pass

    def handle_test_assert_event(self, event):
        pass

    def enter_scope(self):
        self.variables = self.variables.enter()

    def exit_scope(self):
        self.variables = self.variables.exit()

    # noinspection PyUnresolvedReferences
    def get_analysis(self) -> Set[AnalysisObject]:
        return self.factory.get_all()

    def finalize(
        self, passed: Optional[List[EventFile]], failed: Optional[List[EventFile]]
    ):
        for p in self.get_analysis():
            p.analyze(passed, failed)
