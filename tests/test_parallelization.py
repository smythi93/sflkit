import os
from pathlib import Path
from typing import List

from jinja2.nodes import Test
from sflkit import Analyzer, Config, instrument_config
from sflkit.analysis.analysis_type import AnalysisType
from sflkit.analysis.spectra import Spectrum
from sflkit.analysis.suggestion import Location
from sflkit.events.event_file import EventFile
from sflkit.events.mapping import EventMapping
from sflkit.runners import ParallelPytestRunner, RunnerType
from sflkitlib.events.event import DefEvent, LineEvent
from utils import BaseTest


class ParallelizationTest(BaseTest):
    def assertPathExists(self, path: os.PathLike):
        self.assertTrue(os.path.exists(path), f"{path} does not exists.")

    @classmethod
    def create_config(
        cls, test: str, events: str, predicates: str = None, workers: int = 4
    ) -> Config:
        config = Config.create(
            path=os.path.join(BaseTest.TEST_RESOURCES, test),
            language="python",
            events=events,
            predicates=predicates,
            working=BaseTest.TEST_DIR,
            runner=RunnerType.PARALLEL_PYTEST_RUNNER.name,
            workers=workers,
            thread_support=True,
            exclude="tests",
            mapping_path=BaseTest.TEST_MAPPING,
        )
        instrument_config(config)
        return config

    def get_event_files(
        self,
        config: Config,
    ) -> tuple[List[EventFile], List[EventFile]]:
        runner = ParallelPytestRunner(
            set_python_path=True, workers=4, thread_support=True
        )
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(
            Path(BaseTest.TEST_DIR), output, files=[Path("tests", "test_example.py")]
        )
        self.assertPathExists(output)
        self.assertPathExists(output / "passing")
        self.assertPathExists(output / "failing")
        self.assertPathExists(output / "undefined")
        mapping = EventMapping.load(config)
        return (
            [
                EventFile(
                    output / "failing" / os.listdir(output / "failing")[0],
                    0,
                    mapping,
                    failing=True,
                    thread_support=True,
                )
            ],
            [
                EventFile(
                    output / "passing" / path, run_id, mapping, thread_support=True
                )
                for run_id, path in enumerate(os.listdir(output / "passing"), start=1)
            ],
        )

    @staticmethod
    def run_only_analysis(
        failing: List[EventFile], passing: List[EventFile], config: Config
    ) -> Analyzer:
        analyzer = Analyzer(failing, passing, config.factory, parallel=True)
        analyzer.analyze()
        return analyzer

    def run_pytest_analysis(
        self, test: str, events: str, predicates: str, workers: int = 4
    ) -> Analyzer:
        config = self.create_config(
            test=test,
            events=events,
            predicates=predicates,
            workers=workers,
        )
        failing, passing = self.get_event_files(config)
        analyzer = self.run_only_analysis(failing, passing, config)
        return analyzer

    def test_line_suggestions(self):
        analyzer = self.run_pytest_analysis(
            test=BaseTest.TEST_PARALLEL,
            events="line",
            predicates="line",
            workers=4,
        )
        original_dir = os.path.join(self.TEST_RESOURCES, BaseTest.TEST_PARALLEL)
        suggestions = analyzer.get_sorted_suggestions(
            base_dir=original_dir,
            type_=AnalysisType.LINE,
            metric=Spectrum.Tarantula,
        )
        self.assertEqual(len(suggestions), 2)
        self.assertAlmostEqual(1, suggestions[0].suspiciousness, delta=self.DELTA)
        self.assertEqual(1, len(suggestions[0].lines))
        self.assertIn(Location("example.py", 7), suggestions[0].lines)
        self.assertAlmostEqual(0.5, suggestions[1].suspiciousness, delta=self.DELTA)
        self.assertEqual(23, len(suggestions[1].lines))

    MAIN_PATH = (
        [
            LineEvent("example.py", 1, 0),
            DefEvent("example.py", 15, 0, var="numbers"),
            DefEvent("example.py", 15, 0, var="num_threads"),
            LineEvent("example.py", 26, 0),
            DefEvent("example.py", 26, 0, var="results"),
            LineEvent("example.py", 27, 0),
            DefEvent("example.py", 27, 0, var="lock"),
            LineEvent("example.py", 35, 0),
            DefEvent("example.py", 35, 0, var="chunk_size"),
            LineEvent("example.py", 36, 0),
            DefEvent("example.py", 36, 0, var="threads"),
            LineEvent("example.py", 38, 0),
        ]
        + [
            DefEvent("example.py", 38, 0, var="i"),
            LineEvent("example.py", 39, 0),
            DefEvent("example.py", 39, 0, var="start"),
            LineEvent("example.py", 40, 0),
            DefEvent("example.py", 40, 0, var="end"),
            LineEvent("example.py", 41, 0),
            DefEvent("example.py", 41, 0, var="t"),
            LineEvent("example.py", 42, 0),
            LineEvent("example.py", 43, 0),
        ]
        * 2
        + [
            LineEvent("example.py", 45, 0),
            DefEvent("example.py", 45, 0, var="t"),
            LineEvent("example.py", 46, 0),
            DefEvent("example.py", 45, 0, var="t"),
            LineEvent("example.py", 46, 0),
            LineEvent("example.py", 48, 0),
        ]
    )

    THREAD_PATH_START = [
        DefEvent("example.py", 29, 0, var="nums"),
        LineEvent("example.py", 30, 0),
    ]
    THREAD_PATH_LOOP_START = [
        DefEvent("example.py", 30, 0, var="n"),
        LineEvent("example.py", 31, 0),
        DefEvent("example.py", 4, 0, var="n"),
        LineEvent("example.py", 6, 0),
    ]

    THREAD_PATH_LOOP_GT_0 = [
        LineEvent("example.py", 9, 0),
        DefEvent("example.py", 9, 0, var="result"),
        LineEvent("example.py", 10, 0),
    ]
    THREAD_PATH_LOOP_GT_1 = [
        DefEvent("example.py", 10, 0, var="i"),
        LineEvent("example.py", 11, 0),
        DefEvent("example.py", 11, 0, var="result"),
    ]

    THREAD_PATH_LOOP_END = [
        LineEvent("example.py", 12, 0),
        DefEvent("example.py", 31, 0, var="fact"),
        LineEvent("example.py", 32, 0),
        LineEvent("example.py", 33, 0),
    ]

    THREAD_PATH_LOOP_0 = (
        THREAD_PATH_LOOP_START
        + [
            LineEvent("example.py", 7, 0),
            DefEvent("example.py", 7, 0, var="result"),
        ]
        + THREAD_PATH_LOOP_END
    )

    THREAD_PATH_LOOP_1 = (
        THREAD_PATH_LOOP_START + THREAD_PATH_LOOP_GT_0 + THREAD_PATH_LOOP_END
    )
    THREAD_PATH_LOOP_2 = (
        THREAD_PATH_LOOP_START
        + THREAD_PATH_LOOP_GT_0
        + THREAD_PATH_LOOP_GT_1
        + THREAD_PATH_LOOP_END
    )
    THREAD_PATH_LOOP_3 = (
        THREAD_PATH_LOOP_START
        + THREAD_PATH_LOOP_GT_0
        + THREAD_PATH_LOOP_GT_1 * 2
        + THREAD_PATH_LOOP_END
    )
    THREAD_PATH_LOOP_4 = (
        THREAD_PATH_LOOP_START
        + THREAD_PATH_LOOP_GT_0
        + THREAD_PATH_LOOP_GT_1 * 3
        + THREAD_PATH_LOOP_END
    )
    THREAD_PATH_LOOP_5 = (
        THREAD_PATH_LOOP_START
        + THREAD_PATH_LOOP_GT_0
        + THREAD_PATH_LOOP_GT_1 * 4
        + THREAD_PATH_LOOP_END
    )
    THREAD_PATH_LOOP_6 = (
        THREAD_PATH_LOOP_START
        + THREAD_PATH_LOOP_GT_0
        + THREAD_PATH_LOOP_GT_1 * 5
        + THREAD_PATH_LOOP_END
    )
    THREAD_PATH_LOOP_7 = (
        THREAD_PATH_LOOP_START
        + THREAD_PATH_LOOP_GT_0
        + THREAD_PATH_LOOP_GT_1 * 6
        + THREAD_PATH_LOOP_END
    )

    EVENTS_PATHS = {
        "tests_test_example_py__MiddleTests__test_67": {
            0: MAIN_PATH[:],
            1: THREAD_PATH_START[:] + THREAD_PATH_LOOP_6[:],
            2: THREAD_PATH_START[:] + THREAD_PATH_LOOP_7[:],
        },
        "tests_test_example_py__MiddleTests__test_21345": {
            0: MAIN_PATH[:],
            1: THREAD_PATH_START[:] + THREAD_PATH_LOOP_2[:] + THREAD_PATH_LOOP_1[:],
            2: THREAD_PATH_START[:]
            + THREAD_PATH_LOOP_3[:]
            + THREAD_PATH_LOOP_4[:]
            + THREAD_PATH_LOOP_5[:],
        },
        "tests_test_example_py__MiddleTests__test_32106": {
            0: MAIN_PATH[:],
            1: THREAD_PATH_START[:] + THREAD_PATH_LOOP_3[:] + THREAD_PATH_LOOP_2[:],
            2: THREAD_PATH_START[:]
            + THREAD_PATH_LOOP_1[:]
            + THREAD_PATH_LOOP_0[:]
            + THREAD_PATH_LOOP_6,
        },
    }

    def test_parallel_def(self):
        failing, passing = self.get_event_files(
            self.create_config(
                test=BaseTest.TEST_PARALLEL,
                events="line,def",
                workers=4,
            )
        )
        observed = {}

        for ef in failing + passing:
            event_paths = {}
            with ef:
                for ev in ef.load():
                    path = event_paths.setdefault(ev.thread_id, [])
                    path.append(ev)
                observed[os.path.basename(ef.path)] = event_paths

        for test_name, thread_paths in self.EVENTS_PATHS.items():
            for thread_id, expected_events in thread_paths.items():
                observed_events = observed[test_name][thread_id]
                self.assertEqual(
                    len(observed_events),
                    len(expected_events),
                    f"Mismatch in number of events for {test_name} thread {thread_id}",
                )
                for expected_event, observed_event in zip(
                    expected_events, observed_events
                ):
                    if isinstance(expected_event, LineEvent) and isinstance(
                        observed_event, LineEvent
                    ):
                        self.assertEqual(
                            expected_event.file,
                            observed_event.file,
                            f"LineEvent file mismatch in {test_name} thread {thread_id}",
                        )
                        self.assertEqual(
                            expected_event.line,
                            observed_event.line,
                            f"LineEvent mismatch in {test_name} thread {thread_id}",
                        )
                    elif isinstance(expected_event, DefEvent) and isinstance(
                        observed_event, DefEvent
                    ):
                        self.assertEqual(
                            expected_event.file,
                            observed_event.file,
                            f"DefEvent file mismatch in {test_name} thread {thread_id}",
                        )
                        self.assertEqual(
                            expected_event.line,
                            observed_event.line,
                            f"DefEvent line mismatch in {test_name} thread {thread_id}",
                        )
                        self.assertEqual(
                            expected_event.var,
                            observed_event.var,
                            f"DefEvent var mismatch in {test_name} thread {thread_id}",
                        )
                    else:
                        self.fail(
                            f"Event type mismatch in {test_name} thread {thread_id}: "
                            f"expected {type(expected_event)}, got {type(observed_event)}"
                        )
