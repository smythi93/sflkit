from typing import Optional, Set

from sflkitlib.events.event import (
    FunctionEnterEvent,
    FunctionExitEvent,
    FunctionErrorEvent,
    DefEvent,
    UseEvent,
    Event,
)

from sflkit.analysis.analysis_type import AnalysisObject
from sflkit.events.event_file import EventFile
from sflkit.model.model import Model
from sflkit.model.scope import Scope


class ParallelModel(Model):
    def __init__(self, factory, workers: int = 4):
        super().__init__(factory, workers)
        self.variables_map: dict[EventFile, dict[int, Scope]] = dict()
        self.returns_map: dict[EventFile, dict[int, Scope]] = dict()

    def prepare(self, event_file: EventFile):
        super().prepare(event_file)
        self.variables_map = dict()
        self.returns_map = dict()

    def handle_function_enter_event(
        self, event: FunctionEnterEvent, event_file: EventFile
    ):
        if event.thread_id is None:
            self.enter_scope(event_file)
        else:
            self.enter_parallel_scope(event.thread_id, event_file)
        self.handle_event(event, event_file)

    def handle_function_exit_event(
        self, event: FunctionExitEvent, event_file: EventFile
    ):
        if event.thread_id is None:
            self.returns[event_file].add(
                event.function, event.return_value, event.type_
            )
            self.handle_event(event, event_file, self.returns[event_file])
        else:
            self.returns_map[event_file].setdefault(event.thread_id, Scope()).add(
                event.function, event.return_value, event.type_
            )
            self.handle_event(
                event, event_file, self.returns_map[event_file][event.thread_id]
            )
        if event.thread_id is None:
            self.exit_scope(event_file)
        else:
            self.exit_parallel_scope(event.thread_id, event_file)

    def handle_function_error_event(
        self, event: FunctionErrorEvent, event_file: EventFile
    ):
        self.handle_event(event, event_file)
        if event.thread_id is None:
            self.exit_scope(event_file)
        else:
            self.exit_parallel_scope(event.thread_id, event_file)

    def handle_def_event(self, event: DefEvent, event_file: EventFile):
        if event.thread_id is None:
            self.variables[event_file].add(event.var, event.value, event.type_)
            self.handle_event(event, event_file, self.variables[event_file])
        else:
            self.variables_map[event_file].setdefault(
                event.thread_id, self.variables[event_file]
            ).add(event.var, event.value, event.type_)
            self.handle_event(
                event, event_file, self.variables_map[event_file][event.thread_id]
            )

    def handle_use_event(self, event: UseEvent, event_file: EventFile):
        if event.thread_id is None:
            self.handle_event(event, event_file, self.variables[event_file])
        else:
            self.handle_event(
                event,
                event_file,
                self.variables_map[event_file].get(
                    event.thread_id, self.variables[event_file]
                ),
            )

    def enter_parallel_scope(self, thread_id: int, event_file: EventFile):
        self.variables_map[event_file][thread_id] = self.variables_map.get(
            thread_id, self.variables
        ).enter()

    def exit_parallel_scope(self, thread_id: int, event_file: EventFile):
        self.variables_map[event_file][thread_id] = self.variables_map.get(
            thread_id, self.variables
        ).exit()
