from typing import Set, List, Optional

from sflkit.analysis.analysis_type import AnalysisObject
from sflkit.events.event_file import EventFile
from sflkit.model.model import Model
from sflkit.model.scope import Scope


class ParallelModel(Model):
    def __init__(self, factory):
        super().__init__(factory)
        self.variables_map: dict[int, Scope] = dict()
        self.returns_map: dict[int, Scope] = dict()

    def prepare(self, event_file):
        self.factory.reset()
        self.variables = Scope()
        self.returns = Scope()
        self.current_event_file = event_file
        self.variables_map = dict()
        self.returns_map = dict()

    def follow_up(self, event_file):
        pass

    def handle_line_event(self, event):
        self.handle_event(event)

    def handle_branch_event(self, event):
        self.handle_event(event)

    def handle_function_enter_event(self, event):
        if event.thread_id is None:
            self.enter_scope()
        else:
            self.enter_parallel_scope(event.thread_id)
        self.handle_event(event)

    def handle_function_exit_event(self, event):
        if event.thread_id is None:
            self.returns.add(event.function, event.return_value, event.type_)
        else:
            self.returns_map.setdefault(event.thread_id, Scope()).add(
                event.function, event.return_value, event.type_
            )
        self.handle_event(event, self.returns)
        if event.thread_id is None:
            self.exit_scope()
        else:
            self.exit_parallel_scope(event.thread_id)

    def handle_function_error_event(self, event):
        self.handle_event(event)
        if event.thread_id is None:
            self.exit_scope()
        else:
            self.exit_parallel_scope(event.thread_id)

    def handle_def_event(self, event):
        if event.thread_id is None:
            self.variables.add(event.var, event.value, event.type_)
        else:
            self.variables_map.setdefault(event.thread_id, self.variables).add(
                event.var, event.value, event.type_
            )
        self.handle_event(event, self.variables)

    def handle_use_event(self, event):
        if event.thread_id is None:
            self.handle_event(event, self.variables)
        else:
            self.handle_event(
                event, self.variables_map.get(event.thread_id, self.variables)
            )

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

    def enter_parallel_scope(self, thread_id: int):
        self.variables_map[thread_id] = self.variables_map.get(
            thread_id, self.variables
        ).enter()

    def exit_parallel_scope(self, thread_id: int):
        self.variables_map[thread_id] = self.variables_map.get(
            thread_id, self.variables
        ).exit()

    # noinspection PyUnresolvedReferences
    def get_analysis(self) -> Set[AnalysisObject]:
        return self.factory.get_all()

    def finalize(
        self, passed: Optional[List[EventFile]], failed: Optional[List[EventFile]]
    ):
        for p in self.get_analysis():
            p.analyze(passed, failed)
