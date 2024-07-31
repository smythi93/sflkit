import json
import os
from pathlib import Path
from typing import Dict, Optional, Any

from sflkitlib.events.event import Event, load_json, EventEncoder, load

SFLKIT_PATH = Path.home() / ".sflkit"


class InstrumentationError(RuntimeError):
    pass


class EventMapping:
    def __init__(
        self,
        mapping: Dict[int, Event] = None,
        path: Optional[os.PathLike] = None,
        translation: Dict[int, int] = None,
        alternative_mapping: Dict[int, Event] = None,
    ):
        self.original_mapping = mapping or dict()
        self.path = path
        self.translation = translation or {id_: id_ for id_ in self.original_mapping}
        self.valid = set(self.translation.values())
        self.alternative_mapping = alternative_mapping or dict()
        self.mapping = dict()
        self.build_translation()

    def get(self, event_id) -> Optional[Event]:
        return self.mapping.get(event_id, None)

    def build_translation(self):
        if not self.translation:
            self.translation = {
                event_id: event_id for event_id in self.original_mapping
            }
            self.valid = set(self.translation.values())
        self.mapping = dict()
        for id_ in self.translation:
            translated_id = self.translation[id_]
            if translated_id in self.original_mapping:
                self.mapping[id_] = self.original_mapping[translated_id]
        for id_ in self.alternative_mapping:
            if id_ not in self.original_mapping:
                self.mapping[id_] = self.alternative_mapping[id_]

    @staticmethod
    def get_path(identifier: str) -> Path:
        return SFLKIT_PATH / f"{identifier}.json"

    @staticmethod
    def load(config: Any):
        if not hasattr(config, "identifier"):
            raise InstrumentationError(f"Argument does not have an identifier")
        return EventMapping.load_from_file(
            config.mapping_path or EventMapping.get_path(config.identifier()),
            config.target_path,
        )

    @staticmethod
    def load_from_file(file: Path, path: os.PathLike):
        if file.exists():
            return EventMapping(load_json(file), file)
        else:
            raise InstrumentationError(
                f"Cannot find information about instrumentation of {path or file}"
            )

    def write(self, config, indent: Optional[int] = None):
        if not hasattr(config, "identifier"):
            raise InstrumentationError(f"Argument does not have an identifier")
        if self.path:
            file = self.path
        else:
            SFLKIT_PATH.mkdir(parents=True, exist_ok=True)
            file = self.get_path(config.identifier())
        with file.open("w") as fp:
            json.dump(list(self.mapping.values()), fp, cls=EventEncoder, indent=indent)

    def __len__(self):
        return len(self.mapping)

    def load_events(self, event_log: os.PathLike):
        return load(event_log, self.mapping)

    def sorted(self):
        return sorted(list(self.mapping.values()), key=lambda e: e.event_id)

    def __next__(self):
        return next(self.mapping)

    def __iter__(self):
        return iter(self.mapping)

    def is_valid(self, event: Event):
        return event.event_id in self.valid
