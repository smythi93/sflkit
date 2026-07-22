import configparser
import csv
import hashlib
import os.path
import queue
from pathlib import Path
from typing import List, Callable, Union, Optional

from sflkit.analysis.analysis_type import AnalysisType
from sflkit.analysis.factory import (
    analysis_factory_mapping,
    CombinationFactory,
    AnalysisFactory,
)
from sflkit.analysis.mapping import analysis_mapping
from sflkit.analysis.predicate import Predicate
from sflkit.analysis.spectra import Spectrum
from sflkit.language.language import Language
from sflkit.language.meta import (
    CombinationVisitor,
    IDGenerator,
    TmpGenerator,
    MetaVisitor,
)
from sflkit.language.visitor import ASTVisitor
from sflkit.events.mapping import EventMapping, InstrumentationError
from sflkit.events.event_file import EventFile
from sflkit.runners import RunnerType
from sflkitlib.events import EventType


class ConfigError(Exception):
    pass


class Config:
    """
    The basic entry of the config file to start sd tools. The config file follows this form:

    [target]
    path=/path/to/the/subject
    language=Python|C                       : The programming language used

    [events]
    events=Event(,Event)*                   : The events to investigate, overwritten by predicates.
    predicates=Predicate(,Predicate)*        : The predicates to investigate, overwrites events.
    metrics=Metric(,Metric)*                : The metrics used for investigation
    passing=/path(,path)*                   : The event files of passing runs, if a dir is provided
                                              all files inside the tree will be treated as event files
    failing=/path(,path)*                   : The event files of failing runs, if a dir is provided
                                              all files inside the tree will be treated as event files

    [instrumentation]
    path=/path/to/the/instrumented/subject
    include=file(,file)*                    : Files to include in the instrumentation (other files will automatically
                                              be excluded), should be a python re pattern
    exclude=file(,file)*                    : Files to exclude from the instrumentation, should be a python re pattern

    [test]
    runner=TestRunner                       : The testrunner class, None if no run needed
    workers=number_of_workers               : Number of workers for parallel runners
    thread_support=True|False               : Whether the subject uses threading
    """

    def __init__(self, path: Union[str, configparser.ConfigParser] = None):
        self.target_path = None
        self.language: Language = None
        self.predicates = list()
        self.factory = None
        self.test_factory = None
        self.events = list()
        self.test_events = list()
        self.ignore_inner = False
        self.metrics = list()
        self.meta_visitor = None
        self.meta_test_visitor = None
        self.visitor = None
        self.test_visitor = None
        self.passing = list()
        self.failing = list()
        self.instrument_include = list()
        self.instrument_exclude = list()
        self.instrument_test = list()
        self.instrument_test_files = list()
        self.instrument_working = None
        self.runner = None
        self.workers = 1
        self.thread_support = False
        self.mapping = None
        self.mapping_path = None
        self.events_id_generator = IDGenerator()
        self.functions_id_generator = IDGenerator()
        if path:
            if isinstance(path, configparser.ConfigParser):
                config = path
            else:
                config = configparser.ConfigParser()
                config.read(path)
            try:
                # target section
                target = config["target"]
                if "path" in target:
                    self.target_path = Path(target["path"])
                if "language" in target:
                    self.language = Language[target["language"].upper()]
                    self.language.setup()

                # events section
                events = config["events"]
                if "predicates" in events:
                    # get the predicates
                    self.predicates = list(
                        map(
                            lambda p: AnalysisType[p.upper()],
                            list(csv.reader([events["predicates"]]))[0],
                        )
                    )
                    self.factory = CombinationFactory(
                        list(
                            map(
                                lambda p: analysis_factory_mapping[p](), self.predicates
                            )
                        )
                    )
                    # get the events
                    self.events = {
                        e for p in self.predicates for e in analysis_mapping[p].events()
                    }
                elif "events" in events:
                    self.factory = CombinationFactory(list())
                    # get the events
                    self.events = list(
                        map(
                            lambda e: EventType[e.upper()],
                            list(csv.reader([events["events"]]))[0],
                        )
                    )

                if "test" in events:
                    self.test_factory = CombinationFactory(list())
                    # get the events
                    self.test_events = list(
                        map(
                            lambda e: EventType[e.upper()],
                            list(csv.reader([events["test"]]))[0],
                        )
                    )
                if "ignore_inner" in events:
                    self.ignore_inner = events["ignore_inner"].lower() in [
                        "true",
                        "1",
                        "t",
                        "y",
                        "yes",
                    ]

                self.meta_visitor = CombinationVisitor(
                    self.language,
                    self.events_id_generator,
                    self.functions_id_generator,
                    TmpGenerator(),
                    [self.language.meta_visitors[e] for e in self.events],
                )
                self.visitor = self.language.visitor(self.meta_visitor)

                if self.test_events:
                    self.meta_test_visitor = CombinationVisitor(
                        self.language,
                        self.events_id_generator,
                        self.functions_id_generator,
                        TmpGenerator(),
                        [self.language.meta_visitors[e] for e in self.test_events],
                        test=True,
                        ignore_inner=self.ignore_inner,
                    )
                    self.test_visitor = self.language.visitor(self.meta_test_visitor)

                if "metrics" in events:
                    self.metrics = list(
                        map(
                            lambda m: getattr(Predicate, m),
                            list(csv.reader([events["metrics"]]))[0],
                        )
                    )
                else:
                    self.metrics = [Spectrum.Ochiai]

                run_id_generator = IDGenerator()
                if "mapping" in events:
                    self.mapping_path = Path(events["mapping"])
                try:
                    self.mapping = EventMapping.load(self)
                except InstrumentationError:
                    self.mapping = EventMapping(path=self.mapping_path)
                if "passing" in events:
                    self.passing = self.get_event_files(
                        list(csv.reader([events["passing"]]))[0],
                        run_id_generator,
                        self.mapping,
                        False,
                    )
                if "failing" in events:
                    self.failing = self.get_event_files(
                        list(csv.reader([events["failing"]]))[0],
                        run_id_generator,
                        self.mapping,
                        True,
                    )
                # instrumentation section
                instrument = config["instrumentation"]
                if "include" in instrument:
                    self.instrument_include = list(csv.reader([instrument["include"]]))[
                        0
                    ]
                    while "" in self.instrument_include:
                        self.instrument_include.remove("")
                if "exclude" in instrument:
                    self.instrument_exclude = list(csv.reader([instrument["exclude"]]))[
                        0
                    ]
                    while "" in self.instrument_exclude:
                        self.instrument_exclude.remove("")
                if "test" in instrument:
                    self.instrument_test = list(csv.reader([instrument["test"]]))[0]
                    while "" in self.instrument_test:
                        self.instrument_test.remove("")
                if "test_files" in instrument:
                    self.instrument_test_files = list(
                        csv.reader([instrument["test_files"]])
                    )[0]
                    while "" in self.instrument_test:
                        self.instrument_test_files.remove("")
                self.instrument_working = Path(instrument["path"])

                # test section
                if "test" in config:
                    test = config["test"]
                    if "runner" in test and test["runner"] != "None":
                        self.runner = RunnerType[test["runner"].upper()]
                    if "workers" in test:
                        self.workers = int(test["workers"])
                        if (
                            self.workers > 1
                            and self.runner
                            and not self.runner.name.startswith("PARALLEL_")
                        ):
                            self.runner = RunnerType["PARALLEL_" + self.runner.name]
                    if "thread_support" in test:
                        self.thread_support = test["thread_support"].lower() in [
                            "True",
                            "true",
                            "1",
                            "t",
                            "y",
                            "yes",
                        ]

            except KeyError as e:
                raise ConfigError(e)

    @staticmethod
    def create_from_values(
        target_path: Optional[str] = None,
        language: Optional[Language] = None,
        predicates: Optional[List[AnalysisType]] = None,
        factory: Optional[AnalysisFactory] = None,
        test_factory: Optional[AnalysisFactory] = None,
        events: Optional[List[EventType]] = None,
        test_events: Optional[List[EventType]] = None,
        ignore_inner: Optional[bool] = False,
        metrics: Optional[List[Callable]] = None,
        meta_visitor: Optional[MetaVisitor] = None,
        visitor: Optional[ASTVisitor] = None,
        passing: Optional[List[EventFile]] = None,
        failing: Optional[List[EventFile]] = None,
        mapping: Optional[EventMapping] = None,
        instrument_include: Optional[List[str]] = None,
        instrument_exclude: Optional[List[str]] = None,
        instrument_test: Optional[List[str]] = None,
        instrument_working: Optional[str] = None,
        runner: Optional[RunnerType] = None,
        workers: Optional[int] = 1,
        thread_support: Optional[bool] = False,
    ):
        conf = Config()
        conf.target_path = target_path
        conf.language = language
        if language:
            conf.language.setup()
        conf.predicates = predicates or list()
        conf.factory = factory
        conf.test_factory = test_factory
        conf.events = events or list()
        conf.test_events = test_events or list()
        conf.ignore_inner = ignore_inner or False
        conf.metrics = metrics or list()
        conf.meta_visitor = meta_visitor
        conf.visitor = visitor
        conf.passing = passing or list()
        conf.failing = failing or list()
        conf.instrument_include = instrument_include or list()
        conf.instrument_exclude = instrument_exclude or list()
        conf.instrument_test = instrument_test or list()
        conf.instrument_working = instrument_working
        conf.runner = runner
        conf.workers = workers or 1
        conf.thread_support = thread_support
        if mapping:
            conf.mapping = mapping
            if mapping.path:
                conf.mapping_path = mapping.path
        return conf

    @staticmethod
    def get_event_files(files, run_id_generator, mapping: EventMapping, failing):
        file_queue = queue.Queue()
        for f in files:
            file_queue.put(f)
        result = list()
        while not file_queue.empty():
            element = file_queue.get()
            if os.path.exists(element):
                if os.path.isdir(element):
                    for f in os.listdir(element):
                        file_queue.put(os.path.join(element, f))
                elif os.path.isfile(element) and not os.path.islink(element):
                    result.append(
                        EventFile(
                            element,
                            run_id_generator.get_next_id(),
                            mapping,
                            failing=failing,
                        )
                    )
            else:
                result.append(
                    EventFile(
                        element,
                        run_id_generator.get_next_id(),
                        mapping,
                        failing=failing,
                    )
                )
        return result

    @staticmethod
    def create(
        path=None,
        language=None,
        events=None,
        test_events=None,
        ignore_inner=None,
        predicates=None,
        metrics=None,
        passing=None,
        failing=None,
        mapping_path=None,
        working=None,
        include=None,
        exclude=None,
        tests=None,
        test_files=None,
        runner=None,
        workers=None,
        thread_support=None,
    ):
        conf = configparser.ConfigParser()
        conf["target"] = dict()
        conf["events"] = dict()
        conf["instrumentation"] = dict()
        conf["test"] = dict()

        if path:
            conf["target"]["path"] = path
        if language:
            conf["target"]["language"] = language
        if events:
            conf["events"]["events"] = events
        if predicates:
            conf["events"]["predicates"] = predicates
        if test_events:
            conf["events"]["test"] = test_events
        if ignore_inner:
            conf["events"]["ignore_inner"] = ignore_inner
        if metrics:
            conf["events"]["metrics"] = metrics
        if passing:
            conf["events"]["passing"] = passing
        if failing:
            conf["events"]["failing"] = failing
        if mapping_path:
            conf["events"]["mapping"] = mapping_path
        if working:
            conf["instrumentation"]["path"] = working
        if include:
            conf["instrumentation"]["include"] = include
        if exclude:
            conf["instrumentation"]["exclude"] = exclude
        if tests:
            conf["instrumentation"]["test"] = tests
        if test_files:
            conf["instrumentation"]["test_files"] = test_files
        if runner:
            conf["test"]["runner"] = runner
        if workers:
            conf["test"]["workers"] = str(workers)
        if thread_support:
            conf["test"]["thread_support"] = str(thread_support)

        return Config(conf)

    def write(self, path):
        conf = configparser.ConfigParser()
        conf["target"] = dict()
        conf["events"] = dict()
        conf["instrumentation"] = dict()
        conf["test"] = dict()

        if self.target_path:
            conf["target"]["path"] = str(self.target_path)
        if self.language:
            conf["target"]["language"] = self.language.name
        if self.events:
            conf["events"]["events"] = ",".join(e.name for e in self.events)
        if self.test_events:
            conf["events"]["test"] = ",".join(e.name for e in self.test_events)
        if self.ignore_inner:
            conf["events"]["ignore_inner"] = str(self.ignore_inner)
        if self.predicates:
            conf["events"]["predicates"] = ",".join(p.name for p in self.predicates)
        if self.metrics:
            conf["events"]["metrics"] = ",".join(m.__name__ for m in self.metrics)
        if self.passing:
            conf["events"]["passing"] = ",".join(e.path for e in self.passing)
        if self.failing:
            conf["events"]["failing"] = ",".join(e.path for e in self.failing)
        if self.mapping_path:
            conf["events"]["mapping"] = str(self.mapping_path)
        if self.instrument_working:
            conf["instrumentation"]["path"] = str(self.instrument_working)
        if self.instrument_include:
            conf["instrumentation"]["include"] = (
                '"' + '","'.join(self.instrument_include) + '"'
            )
        if self.instrument_exclude:
            conf["instrumentation"]["exclude"] = (
                '"' + '","'.join(self.instrument_exclude) + '"'
            )
        if self.instrument_test:
            conf["instrumentation"]["test"] = (
                '"' + '","'.join(self.instrument_test) + '"'
            )
        if self.instrument_test_files:
            conf["instrumentation"]["test_files"] = (
                '"' + '","'.join(self.instrument_test_files) + '"'
            )
        if self.runner:
            conf["test"]["runner"] = self.runner.name
        if self.workers:
            conf["test"]["workers"] = str(self.workers)
        if self.thread_support:
            conf["test"]["thread_support"] = str(self.thread_support)

        with open(path, "w") as fp:
            conf.write(fp)

    def identifier(self):
        return hash_identifier(self.target_path)


def hash_identifier(path: os.PathLike):
    return hashlib.md5(str(path).encode("utf-8")).hexdigest()


def parse_config(path: str) -> Config:
    return Config(path)


def write_config(config: Config, path: str):
    config.write(path)
