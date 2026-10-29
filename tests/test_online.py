"""
Tests for online (in-process) artifact construction.

The load-bearing test is equivalence: for the same subject and the same input,
the events a tracer materializes must be the events instrumentation writes into
a trace. Everything else the online path produces is built by the existing
analysis layer from those events, so if the events agree, the artifacts agree.
"""

import os
import runpy
import shutil
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from typing import List, Optional

from sflkitlib.events import EventType
from sflkitlib.events.event import Event

from sflkit import Config, instrument_config
from sflkit.analysis.analysis_type import AnalysisType
from sflkit.events.event_file import EventFile
from sflkit.events.mapping import EventMapping
from sflkit.features.handler import EventHandler
from sflkit.features.value import FeatureValue, feature_id
from sflkit.online import (
    EventListener,
    ListenerGroup,
    LocationIndex,
    MonitoringTracer,
    OnlineSession,
    RunArtifact,
    SUPPORTED_EVENT_TYPES,
    SpectrumListener,
    Suite,
    SysTraceTracer,
    TreeBuilder,
    TreeNode,
    get_tracer,
    trace,
)
from sflkit.online.tracer import value_and_type
from sflkit.runners import RunnerType
from sflkit.runners.run import OnlinePytestRunner, PytestRunner, TestResult
from utils import BaseTest


class RecordingListener(EventListener):
    """Keeps every event it is given, for comparison against a trace."""

    def __init__(self):
        self.events: List[Event] = list()
        self.runs: List[EventFile] = list()

    def start(self, run: EventFile) -> None:
        self.runs.append(run)

    def event(self, event: Event) -> None:
        self.events.append(event)


class OnlineTest(BaseTest):
    """Shared plumbing: instrument a subject, then run it offline and online."""

    ALL_EVENTS = (
        "line,branch,def,use,len,loop_begin,loop_hit,loop_end,"
        "function_enter,function_exit,function_error"
    )

    def setUp(self):
        self.work = Path(self.TEST_DIR)
        shutil.rmtree(self.work, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)
        for leftover in (self.TEST_MAPPING, self.TEST_PATH):
            if os.path.exists(leftover):
                os.remove(leftover)

    def instrument(self, subject: str, events: str = None, predicates: str = ""):
        """
        Instrument *subject* and return its config, mapping and source directory.

        The tracer runs the ORIGINAL sources, so the source directory it is
        pointed at is the subject itself, not the instrumented copy.
        """
        source = Path(self.TEST_RESOURCES) / subject
        config = Config.create(
            path=str(source),
            language="python",
            events=events or self.ALL_EVENTS,
            predicates=predicates,
            working=str(self.work),
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        return config, EventMapping.load(config), source

    def offline_events(self, config, mapping, args: List[str]) -> List[Event]:
        """Run the instrumented copy in a subprocess and decode its trace."""
        subprocess.run(
            [self.PYTHON, self.ACCESS] + args,
            cwd=self.work,
            env=os.environ,
            check=False,
        )
        trace_path = self.work / self.TEST_PATH
        with EventFile(trace_path, 0, mapping) as event_file:
            return list(event_file.load())

    def online_events(
        self,
        source: Path,
        mapping: EventMapping,
        args: List[str],
        prefer_monitoring: bool = True,
        thread_support: bool = False,
    ) -> List[Event]:
        """Run the original sources in this process under a tracer."""
        listener = RecordingListener()
        index = LocationIndex(mapping, source)
        tracer = get_tracer(
            index,
            listener,
            thread_support=thread_support,
            prefer_monitoring=prefer_monitoring,
        )
        listener.start(EventFile(Path("online"), 0, None, False))
        self.execute(source, args, tracer)
        return listener.events

    @staticmethod
    def execute(source: Path, args: List[str], tracer) -> None:
        """Execute ``main.py`` of *source* with *args* under *tracer*."""
        argv = sys.argv
        sys.argv = [str(source / "main.py")] + args
        try:
            with tracer:
                try:
                    runpy.run_path(str(source / "main.py"), run_name="__main__")
                except SystemExit:
                    pass
        finally:
            sys.argv = argv

    @staticmethod
    def ids(events: List[Event]) -> List[int]:
        """Event ids of the events a tracer is able to materialize."""
        return [
            event.event_id
            for event in events
            if event.event_type in SUPPORTED_EVENT_TYPES
        ]


class EquivalenceTest(OnlineTest):
    """The tracer must reproduce the instrumented trace."""

    def test_event_sequence_matches_trace(self):
        config, mapping, source = self.instrument(self.TEST_SUGGESTIONS)
        offline = self.offline_events(config, mapping, ["3", "2", "1"])
        online = self.online_events(source, mapping, ["3", "2", "1"])
        self.assertEqual(self.ids(offline), self.ids(online))

    def test_event_sequence_matches_trace_with_settrace(self):
        config, mapping, source = self.instrument(self.TEST_SUGGESTIONS)
        offline = self.offline_events(config, mapping, ["3", "2", "1"])
        online = self.online_events(
            source, mapping, ["3", "2", "1"], prefer_monitoring=False
        )
        self.assertEqual(self.ids(offline), self.ids(online))

    def test_def_events_carry_the_assigned_value(self):
        config, mapping, source = self.instrument(self.TEST_SUGGESTIONS)
        offline = self.offline_events(config, mapping, ["3", "2", "1"])
        online = self.online_events(source, mapping, ["3", "2", "1"])
        expected = [
            (event.event_id, event.var, event.value, event.type_)
            for event in offline
            if event.event_type is EventType.DEF
        ]
        actual = [
            (event.event_id, event.var, event.value, event.type_)
            for event in online
            if event.event_type is EventType.DEF
        ]
        self.assertEqual(expected, actual)
        self.assertTrue(expected, "subject produced no def events")

    def test_function_exit_events_carry_the_return_value(self):
        config, mapping, source = self.instrument(self.TEST_SUGGESTIONS)
        offline = self.offline_events(config, mapping, ["3", "2", "1"])
        online = self.online_events(source, mapping, ["3", "2", "1"])
        expected = [
            (event.event_id, event.return_value, event.type_)
            for event in offline
            if event.event_type is EventType.FUNCTION_EXIT
        ]
        actual = [
            (event.event_id, event.return_value, event.type_)
            for event in online
            if event.event_type is EventType.FUNCTION_EXIT
        ]
        self.assertEqual(expected, actual)
        self.assertTrue(expected, "subject produced no function exit events")

    def test_loops_match_trace(self):
        config, mapping, source = self.instrument(self.TEST_LOOP)
        offline = self.offline_events(config, mapping, ["abc"])
        online = self.online_events(source, mapping, ["abc"])
        self.assertEqual(self.ids(offline), self.ids(online))

    def test_len_events_match_trace(self):
        config, mapping, source = self.instrument(self.TEST_LEN)
        offline = self.offline_events(config, mapping, ["abc"])
        online = self.online_events(source, mapping, ["abc"])
        self.assertEqual(
            [(e.event_id, e.length) for e in offline if e.event_type is EventType.LEN],
            [(e.event_id, e.length) for e in online if e.event_type is EventType.LEN],
        )

    def test_function_error_matches_trace(self):
        config, mapping, source = self.instrument(self.TEST_ERROR)
        offline = self.offline_events(config, mapping, ["0"])
        online = self.online_events(source, mapping, ["0"])
        self.assertEqual(self.ids(offline), self.ids(online))

    def test_conditions_are_reported_as_unsupported(self):
        _, mapping, source = self.instrument(self.TEST_SUGGESTIONS, events="condition")
        index = LocationIndex(mapping, source)
        self.assertIn(EventType.CONDITION, index.skipped)


class VectorTest(OnlineTest):
    """Feature vectors built online must equal those built from a trace."""

    def test_feature_vector_matches_offline(self):
        config, mapping, source = self.instrument(self.TEST_SUGGESTIONS)
        self.offline_events(config, mapping, ["3", "2", "1"])
        handler = EventHandler()
        handler.handle(EventFile(self.work / self.TEST_PATH, 0, mapping, True))
        offline_vector = handler.builder.get_vectors()[0]

        with trace(mapping, source, name="middle", failing=True) as session:
            self.execute(source, ["3", "2", "1"], session.tracer)
        artifact = session.artifact()

        expected = {
            feature.name: value.value
            for feature, value in offline_vector.get_features().items()
            if feature.analysis.analysis_type() not in (AnalysisType.CONDITION,)
        }
        actual = {
            artifact.catalog[fid]: value for fid, value in artifact.features.items()
        }
        self.assertTrue(expected, "offline run produced no features")
        self.assertEqual(expected, actual)

    def test_artifact_result_follows_the_verdict(self):
        _, mapping, source = self.instrument(self.TEST_SUGGESTIONS)
        with trace(mapping, source, name="t", failing=False) as session:
            self.execute(source, ["3", "2", "1"], session.tracer)
        self.assertEqual(TestResult.PASSING, session.artifact().result)
        with trace(mapping, source, name="t", failing=None) as session:
            self.execute(source, ["3", "2", "1"], session.tracer)
        self.assertEqual(TestResult.UNDEFINED, session.artifact().result)


class SpectrumTest(OnlineTest):
    """Spectra built online must equal those built from a trace."""

    def test_spectra_match_offline(self):
        config, mapping, source = self.instrument(
            self.TEST_SUGGESTIONS, events="line,branch", predicates="line,branch"
        )
        offline = self.offline_events(config, mapping, ["3", "2", "1"])
        self.assertTrue(offline)

        listener = SpectrumListener(types=[AnalysisType.LINE, AnalysisType.BRANCH])
        index = LocationIndex(mapping, source)
        tracer = get_tracer(index, listener)
        run = EventFile(Path("online"), 0, None, True)
        listener.start(run)
        self.execute(source, ["3", "2", "1"], tracer)
        listener.stop()
        listener.finalize([], [run])

        online_names = {str(analysis) for analysis in listener.analysis}
        from sflkit.analysis.analyzer import Analyzer

        analyzer = Analyzer(
            [EventFile(self.work / self.TEST_PATH, 0, mapping, True)],
            [],
            config.factory,
        )
        analyzer.analyze()
        offline_names = {str(analysis) for analysis in analyzer.get_analysis()}
        self.assertTrue(offline_names)
        self.assertEqual(offline_names, online_names)


class TreeTest(OnlineTest):
    """The call tree must be built online and merge across runs."""

    def test_tree_records_functions_with_observations(self):
        _, mapping, source = self.instrument(self.TEST_SUGGESTIONS)
        with trace(mapping, source, name="t", failing=True) as session:
            self.execute(source, ["3", "2", "1"], session.tracer)
        tree = session.artifact().tree
        names = {node.name for node in tree.walk()}
        self.assertTrue(
            any("middle" in name for name in names),
            f"middle not recorded in {names}",
        )
        middle = next(node for node in tree.walk() if "middle" in node.name)
        self.assertTrue(middle.enter, "no entry observation recorded")
        self.assertTrue(middle.exit, "no exit observation recorded")
        self.assertTrue(
            all(isinstance(key, int) for key in middle.enter[0]),
            "observations must be keyed by feature id",
        )

    def test_trees_merge_across_runs(self):
        _, mapping, source = self.instrument(self.TEST_SUGGESTIONS)
        artifacts = []
        for index, (args, failing) in enumerate(
            ([["3", "2", "1"], True], [["1", "2", "3"], False])
        ):
            with trace(mapping, source, name=f"t{index}", failing=failing) as session:
                self.execute(source, args, session.tracer)
            artifacts.append(session.artifact())

        suite = Suite.merge(artifacts)
        self.assertEqual(
            [TestResult.FAILING, TestResult.PASSING],
            [artifact.result for artifact in suite.runs],
            "failing runs must merge first",
        )
        merged = next(node for node in suite.tree.walk() if "middle" in node.name)
        separate = [
            next(node for node in artifact.tree.walk() if "middle" in node.name)
            for artifact in artifacts
        ]
        self.assertEqual(
            sum(len(node.enter) for node in separate),
            len(merged.enter),
            "merging must keep every run's observations",
        )

    def test_merge_is_order_independent(self):
        a, b = TreeNode("ROOT"), TreeNode("ROOT")
        a.child("f").enter.append({1: 1})
        b.child("g").enter.append({2: 0})
        forward, backward = TreeNode("ROOT"), TreeNode("ROOT")
        forward.merge(a)
        forward.merge(b)
        backward.merge(b)
        backward.merge(a)
        self.assertEqual(
            sorted(node.name for node in forward.walk()),
            sorted(node.name for node in backward.walk()),
        )

    def test_observations_are_capped_per_run(self):
        _, mapping, source = self.instrument(self.TEST_LOOP)
        with trace(mapping, source, name="t", failing=True) as session:
            self.execute(source, ["abcdefghij"], session.tracer)
        tree = session.artifact().tree
        for node in tree.walk():
            self.assertLessEqual(
                len(node.enter), session.builder.per_run_cap, f"{node.name} uncapped"
            )


class ThreadTest(OnlineTest):
    """Threaded subjects must not have their scopes mixed up."""

    SUBJECT = "test_online_threads"

    def setUp(self):
        super().setUp()
        self.source = Path(self.TEST_RESOURCES) / self.SUBJECT
        self.source.mkdir(parents=True, exist_ok=True)
        (self.source / "main.py").write_text(
            "import threading\n"
            "\n"
            "\n"
            "def work(n):\n"
            "    total = 0\n"
            "    for i in range(n):\n"
            "        total += i\n"
            "    return total\n"
            "\n"
            "\n"
            "threads = [threading.Thread(target=work, args=(3,)) for _ in range(3)]\n"
            "for t in threads:\n"
            "    t.start()\n"
            "for t in threads:\n"
            "    t.join()\n"
        )

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.source, ignore_errors=True)

    def test_events_from_threads_carry_distinct_ids(self):
        _, mapping, source = self.instrument(self.SUBJECT)
        listener = RecordingListener()
        tracer = get_tracer(
            LocationIndex(mapping, source), listener, thread_support=True
        )
        listener.start(EventFile(Path("online"), 0, None, False))
        self.execute(source, [], tracer)
        thread_ids = {event.thread_id for event in listener.events}
        self.assertGreater(
            len(thread_ids), 1, f"expected several threads, saw {thread_ids}"
        )
        self.assertNotIn(None, thread_ids)

    def test_thread_ids_are_absent_without_thread_support(self):
        _, mapping, source = self.instrument(self.SUBJECT)
        listener = RecordingListener()
        tracer = get_tracer(
            LocationIndex(mapping, source), listener, thread_support=False
        )
        listener.start(EventFile(Path("online"), 0, None, False))
        self.execute(source, [], tracer)
        self.assertEqual({None}, {event.thread_id for event in listener.events})

    def test_tree_keeps_one_stack_per_thread(self):
        _, mapping, source = self.instrument(self.SUBJECT)
        with trace(
            mapping, source, name="t", failing=True, thread_support=True
        ) as session:
            self.execute(source, [], session.tracer)
        tree = session.artifact().tree
        work = [node for node in tree.walk() if "work" in node.name]
        self.assertEqual(
            1, len(work), "one function must yield one node regardless of threads"
        )
        self.assertEqual(
            len(work[0].enter),
            len(work[0].exit),
            "every entry must have a matching exit",
        )


class ArtifactTest(OnlineTest):
    """Artifacts must survive the trip between processes."""

    def test_feature_ids_are_stable_across_processes(self):
        name = "Line(main.py:12)"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from sflkit.features.value import feature_id;"
                f"print(feature_id({name!r}))",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": "1"},
        )
        self.assertEqual(str(feature_id(name)), result.stdout.strip())

    def test_artifact_round_trips(self):
        _, mapping, source = self.instrument(self.TEST_SUGGESTIONS)
        with trace(mapping, source, name="t", failing=True) as session:
            self.execute(source, ["3", "2", "1"], session.tracer)
        artifact = session.artifact()
        path = self.work / "artifact.pkl"
        self.work.mkdir(parents=True, exist_ok=True)
        artifact.dump(path)
        loaded = RunArtifact.load(path)
        self.assertEqual(artifact.run, loaded.run)
        self.assertEqual(artifact.result, loaded.result)
        self.assertEqual(artifact.features, loaded.features)
        self.assertEqual(
            [node.name for node in artifact.tree.walk()],
            [node.name for node in loaded.tree.walk()],
        )

    def test_artifact_reads_uncompressed(self):
        artifact = RunArtifact("t", TestResult.FAILING, {1: 1}, {1: "f"})
        path = self.work / "plain.pkl"
        self.work.mkdir(parents=True, exist_ok=True)
        artifact.dump(path, compress=False)
        self.assertEqual({1: 1}, RunArtifact.load(path).features)

    def test_counts_aggregate_runs(self):
        suite = Suite.merge(
            [
                RunArtifact("f", TestResult.FAILING, {1: 1, 2: 0}, {1: "a", 2: "b"}),
                RunArtifact("p", TestResult.PASSING, {1: 1}, {1: "a", 2: "b"}),
            ]
        )
        counts = suite.counts()
        self.assertEqual({"ef": 1, "nf": 0, "ep": 1, "np": 0}, counts[1])
        self.assertEqual({"ef": 0, "nf": 1, "ep": 0, "np": 1}, counts[2])


class BackendTest(OnlineTest):
    """Both backends must be selectable and clean up after themselves."""

    def test_get_tracer_prefers_monitoring_when_available(self):
        _, mapping, source = self.instrument(self.TEST_LINES)
        index = LocationIndex(mapping, source)
        tracer = get_tracer(index, RecordingListener())
        expected = MonitoringTracer if MonitoringTracer.available() else SysTraceTracer
        self.assertIsInstance(tracer, expected)

    def test_monitoring_tracer_releases_its_tool_id(self):
        if not MonitoringTracer.available():
            self.skipTest("sys.monitoring is unavailable")
        _, mapping, source = self.instrument(self.TEST_LINES)
        index = LocationIndex(mapping, source)
        for _ in range(3):
            tracer = MonitoringTracer(index, RecordingListener())
            tracer.start()
            tracer.stop()
        self.assertFalse(tracer.running)

    def test_settrace_tracer_restores_the_previous_hook(self):
        _, mapping, source = self.instrument(self.TEST_LINES)
        tracer = SysTraceTracer(LocationIndex(mapping, source), RecordingListener())
        before = sys.gettrace()
        tracer.start()
        tracer.stop()
        self.assertIs(before, sys.gettrace())

    def test_listener_failures_do_not_reach_the_subject(self):
        class Broken(EventListener):
            def event(self, event):
                raise RuntimeError("listener is broken")

        _, mapping, source = self.instrument(self.TEST_LINES)
        tracer = get_tracer(LocationIndex(mapping, source), Broken())
        # A broken listener must cost events, never the run.
        self.execute(source, [], tracer)


if __name__ == "__main__":
    unittest.main()


class RunnerIntegrationTest(BaseTest):
    """The runner must be able to collect artifacts instead of traces."""

    def setUp(self):
        self.work = Path(self.TEST_DIR)
        self.subject = Path(self.TEST_DIR_2)
        shutil.rmtree(self.work, ignore_errors=True)
        shutil.rmtree(self.subject, ignore_errors=True)
        # The tracer runs the subject as shipped, so the tests execute against
        # a copy of the original sources; instrumentation only supplies the
        # event mapping.
        shutil.copytree(Path(self.TEST_RESOURCES) / self.TEST_RUNNER, self.subject)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)
        shutil.rmtree(self.subject, ignore_errors=True)
        for leftover in (self.TEST_MAPPING, self.TEST_PATH):
            if os.path.exists(leftover):
                os.remove(leftover)

    def _mapping(self):
        config = Config.create(
            path=str(Path(self.TEST_RESOURCES) / self.TEST_RUNNER),
            language="python",
            events="line,branch,def,use,function_enter,function_exit",
            predicates="",
            working=str(self.work),
            exclude="tests",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        return config

    def _run(self, runner):
        output = (self.subject / "events").absolute()
        runner.run(self.subject, output, files=[Path("tests", "test_middle.py")])
        return output

    def test_runner_collects_artifacts_instead_of_traces(self):
        self._mapping()
        runner = OnlinePytestRunner(
            set_python_path=True,
            mapping_path=self.TEST_MAPPING,
            root=self.subject,
        )
        output = self._run(runner)
        self.assertTrue(runner.failing_tests, "no failing test was found")
        self.assertTrue(runner.passing_tests, "no passing test was found")

        artifacts = []
        for result in (TestResult.PASSING, TestResult.FAILING):
            directory = output / result.get_dir()
            self.assertTrue(list(directory.iterdir()), f"no artifact in {directory}")
            for path in directory.iterdir():
                artifact = RunArtifact.load(path)
                self.assertEqual(result, artifact.result)
                self.assertTrue(artifact.features, f"{artifact.run} observed nothing")
                artifacts.append(artifact)

        suite = Suite.merge(artifacts)
        self.assertEqual(
            TestResult.FAILING,
            suite.runs[0].result,
            "failing runs must come first in a merged suite",
        )
        counts = suite.counts()
        self.assertTrue(counts)
        discriminating = [
            feature_id
            for feature_id, count in counts.items()
            if count["ef"] > 0 and count["ep"] == 0
        ]
        self.assertTrue(
            discriminating, "no feature separates the failing run from the passing ones"
        )

    def test_no_traces_are_written(self):
        self._mapping()
        runner = OnlinePytestRunner(
            set_python_path=True,
            mapping_path=self.TEST_MAPPING,
            root=self.subject,
        )
        self._run(runner)
        self.assertFalse(
            list(self.subject.rglob("EVENTS_PATH")),
            "online collection must not write event traces",
        )

    def test_plugin_is_only_loaded_when_online(self):
        offline = PytestRunner()
        online = OnlinePytestRunner(mapping_path=self.TEST_MAPPING, root=self.subject)
        self.assertEqual([], offline.pytest_args())
        self.assertEqual(["-p", "sflkit.online.plugin"], online.pytest_args())

    def test_online_needs_a_mapping(self):
        runner = PytestRunner(online=True)
        with self.assertRaises(ValueError):
            runner.online_environ(self.subject)

    def test_runner_type_exposes_the_online_runner(self):
        self.assertIs(OnlinePytestRunner, RunnerType["ONLINE_PYTEST_RUNNER"].runner)


class ProcessParallelTreeTest(OnlineTest):
    """A tree built in pieces must equal one built in a single pass."""

    def _event_files(self, mapping, args):
        files = []
        for index, arguments in enumerate(args):
            self.offline_events(None, mapping, arguments)
            target = self.work / f"run_{index}"
            shutil.move(self.work / self.TEST_PATH, target)
            files.append(EventFile(target, index, mapping, index == 0))
        return files

    @staticmethod
    def _shape(builder):
        return sorted(
            (node.name, len(node.enter), len(node.exit)) for node in builder.root.walk()
        )

    def test_tree_matches_a_single_process(self):
        _, mapping, _ = self.instrument(self.TEST_SUGGESTIONS)
        event_files = self._event_files(
            mapping, [["3", "2", "1"], ["1", "2", "3"], ["2", "1", "3"]]
        )
        serial = EventHandler(workers=1)
        serial.builder = TreeBuilder()
        serial.model = type(serial.model)(serial.builder)
        serial.handle_files(event_files)

        parallel = EventHandler(workers=1, processes=2)
        parallel.builder = TreeBuilder()
        parallel.model = type(parallel.model)(parallel.builder)
        parallel.handle_files(event_files)

        self.assertTrue(
            any("middle" in name for name, _, _ in self._shape(serial.builder)),
            "the subject produced no tree",
        )
        self.assertEqual(self._shape(serial.builder), self._shape(parallel.builder))
        self.assertEqual(serial.builder.catalog, parallel.builder.catalog)


class BudgetTest(OnlineTest):
    """
    The tracer must respect the same trace budgets as the instrumented runtime.

    Without them the two collection paths diverge on any loop that runs more
    than the budget allows: the runtime stops recording hits while the tracer
    keeps going, so online spectra would be strictly richer than offline ones
    and the two would no longer be comparable.
    """

    def setUp(self):
        super().setUp()
        self._environ = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._environ)
        super().tearDown()

    def _loop_hits(self, events):
        return len([e for e in events if e.event_type is EventType.LOOP_HIT])

    def test_loop_hits_are_capped(self):
        os.environ["EVENTS_MAX_LOOP_HITS"] = "1"
        _, mapping, source = self.instrument(self.TEST_LOOP)
        events = self.online_events(source, mapping, ["abcdefgh"])
        self.assertEqual(
            1, self._loop_hits(events), "hits beyond the budget must be dropped"
        )

    def test_loop_hits_are_unbounded_when_the_budget_is_off(self):
        os.environ["EVENTS_MAX_LOOP_HITS"] = "0"
        _, mapping, source = self.instrument(self.TEST_LOOP)
        events = self.online_events(source, mapping, ["abcdefgh"])
        self.assertEqual(
            8, self._loop_hits(events), "a disabled budget must record every hit"
        )

    def test_oversized_values_are_truncated(self):
        self.assertEqual(("abcd", "str"), value_and_type("abcdefgh", 4))
        self.assertEqual((b"ab", "bytes"), value_and_type(b"abcdef", 2))
        self.assertEqual(("abcdefgh", "str"), value_and_type("abcdefgh", 0))

    def test_numbers_are_never_truncated(self):
        # A number has no prefix to keep, and asking for its length raises.
        self.assertEqual((123456789, "int"), value_and_type(123456789, 2))
        self.assertEqual((1.5, "float"), value_and_type(1.5, 2))
        self.assertEqual((None, "NoneType"), value_and_type(None, 2))
