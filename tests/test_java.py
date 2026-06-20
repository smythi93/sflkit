"""Tests for the Java (jast-based) instrumentation pipeline.

Covers, for the Java language backend:
  * ``Language.JAVA`` wiring (visitor, factories, extractors, finders, suffixes),
  * per-event-type instrumentation (the event mapping produced for each
    ``EventType``),
  * the location finders (function / loop / branch),
  * an end-to-end pipeline (instrument -> compile with jsflkit.jar -> run ->
    decode the trace with sflkitlib), gated on a JDK being available, and
  * documented known limitations (``expectedFailure``) for the parts of the
    reconciliation that are still open (for-loop clause scoping).
"""

import glob
import os
import shutil
import subprocess
import tempfile
import unittest

from sflkit import Config, instrument_config
from sflkit.events.mapping import EventMapping
from sflkit.language.language import Language
from sflkit.language.java.finder import (
    JavaFunctionFinder,
    JavaLoopFinder,
    JavaBranchFinder,
)
from sflkitlib.events import EventType
from sflkitlib.events import event as eventlib
from sflkitlib.events.event import (
    LineEvent,
    BranchEvent,
    DefEvent,
    UseEvent,
    ConditionEvent,
    FunctionEnterEvent,
    FunctionExitEvent,
    FunctionErrorEvent,
    LoopBeginEvent,
    LoopHitEvent,
    LoopEndEvent,
    LenEvent,
)

from utils import PROJECT_DIR

RESOURCES = os.path.join(PROJECT_DIR, "resources", "subjects", "tests")


def _find_jdk():
    """Return (javac, java) for an available JDK (>= 8), or (None, None)."""
    homes = []
    if os.environ.get("JAVA_HOME"):
        homes.append(os.environ["JAVA_HOME"])
    homes.append(os.path.expanduser("~/.jenv/versions/1.8"))
    for home in homes:
        javac = os.path.join(home, "bin", "javac")
        java = os.path.join(home, "bin", "java")
        if os.path.isfile(javac) and os.path.isfile(java):
            return javac, java
    javac, java = shutil.which("javac"), shutil.which("java")
    if javac and java:
        return javac, java
    return None, None


JAVAC, JAVA = _find_jdk()
HAVE_JDK = JAVAC is not None


def _ensure_jar():
    """Return a path to jsflkit.jar, building it from source if necessary."""
    prebuilt = os.path.join(PROJECT_DIR, "jsflkit", "jsflkit.jar")
    if os.path.isfile(prebuilt):
        return prebuilt
    if not HAVE_JDK:
        return None
    src_root = os.path.join(PROJECT_DIR, "jsflkit", "src", "main", "java")
    if not os.path.isdir(src_root):
        return None
    out = tempfile.mkdtemp(prefix="jsflkit_classes_")
    sources = [
        os.path.join(dp, f)
        for dp, _, fs in os.walk(src_root)
        for f in fs
        if f.endswith(".java")
    ]
    if subprocess.run([JAVAC, "-encoding", "UTF-8", "-d", out] + sources).returncode:
        return None
    jar_path = os.path.join(out, "jsflkit.jar")
    jar_tool = os.path.join(os.path.dirname(JAVAC), "jar")
    subprocess.run([jar_tool, "cf", jar_path, "-C", out, "."])
    return jar_path


def _instrument_mapping(work, mapping_path, subject, events):
    """Instrument ``subject`` for ``events`` and return the sorted event mapping."""
    config = Config.create(
        path=os.path.join(RESOURCES, subject),
        language="java",
        events=",".join(e.name.lower() for e in events),
        working=work,
        mapping_path=mapping_path,
    )
    instrument_config(config)
    return config, EventMapping.load(config).sorted()


def _select(events, cls, key):
    return sorted(key(e) for e in events if isinstance(e, cls))


class JavaLanguageWiringTest(unittest.TestCase):
    def test_java_is_wired(self):
        lang = Language.JAVA
        self.assertIsNotNone(lang.visitor)
        self.assertIsNotNone(lang.var_extract)
        self.assertIsNotNone(lang.use_extract)
        self.assertIsNotNone(lang.condition_extract)
        self.assertEqual(["java"], lang.suffixes)

    def test_java_has_all_event_factories(self):
        factories = Language.JAVA.meta_visitors
        for event_type in [
            EventType.LINE,
            EventType.BRANCH,
            EventType.DEF,
            EventType.USE,
            EventType.CONDITION,
            EventType.FUNCTION_ENTER,
            EventType.FUNCTION_EXIT,
            EventType.FUNCTION_ERROR,
            EventType.LOOP_BEGIN,
            EventType.LOOP_HIT,
            EventType.LOOP_END,
            EventType.LEN,
            EventType.TEST_LINE,
            EventType.TEST_DEF,
            EventType.TEST_USE,
            EventType.TEST_ASSERT,
        ]:
            self.assertIn(event_type, factories)

    def test_setup_sets_java_finders(self):
        from sflkit.analysis.analysis_type import AnalysisObject

        Language.JAVA.setup()
        self.assertIs(AnalysisObject.function_finder, JavaFunctionFinder)
        self.assertIs(AnalysisObject.loop_finder, JavaLoopFinder)
        self.assertIs(AnalysisObject.branch_finder, JavaBranchFinder)


class JavaInstrumentationMappingTest(unittest.TestCase):
    SUBJECT = "test_java"
    LOOPS = "test_java_loops"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sflkit_java_")
        self.work = os.path.join(self.tmp, "work")
        self.mapping_path = os.path.join(self.tmp, "mapping.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _map(self, events, subject=None):
        _, mapping = _instrument_mapping(
            self.work, self.mapping_path, subject or self.SUBJECT, events
        )
        return mapping

    def test_lines(self):
        events = self._map([EventType.LINE])
        self.assertEqual(
            [3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 17, 21, 22],
            _select(events, LineEvent, lambda e: e.line),
        )

    def test_branches(self):
        events = self._map([EventType.BRANCH])
        self.assertEqual(
            [
                (4, 0, 1),
                (4, 1, 0),
                (5, 2, 3),
                (5, 3, 2),
                (7, 4, 5),
                (7, 5, 4),
                (11, 6, 7),
                (11, 7, 6),
                (13, 8, 9),
                (13, 9, 8),
            ],
            _select(events, BranchEvent, lambda e: (e.line, e.then_id, e.else_id)),
        )

    def test_defs(self):
        events = self._map([EventType.DEF])
        self.assertEqual(
            [
                (2, "x"),
                (2, "y"),
                (2, "z"),
                (3, "m"),
                (6, "m"),
                (8, "m"),
                (12, "m"),
                (14, "m"),
                (20, "args"),
                (21, "a"),
                (22, "b"),
            ],
            _select(events, DefEvent, lambda e: (e.line, e.var)),
        )

    def test_uses(self):
        events = self._map([EventType.USE])
        self.assertEqual(
            [
                (4, "y"),
                (4, "z"),
                (5, "x"),
                (5, "y"),
                (6, "y"),
                (7, "x"),
                (7, "z"),
                (8, "x"),
                (11, "x"),
                (11, "y"),
                (12, "y"),
                (13, "x"),
                (13, "z"),
                (14, "x"),
                (17, "m"),
            ],
            _select(events, UseEvent, lambda e: (e.line, e.var)),
        )

    def test_conditions(self):
        events = self._map([EventType.CONDITION])
        self.assertEqual(
            [
                (4, "y < z"),
                (5, "x < y"),
                (7, "x < z"),
                (11, "x > y"),
                (13, "x > z"),
            ],
            _select(events, ConditionEvent, lambda e: (e.line, e.condition)),
        )

    def test_function_enter(self):
        events = self._map([EventType.FUNCTION_ENTER])
        self.assertEqual(
            [(2, "middle"), (20, "main")],
            _select(events, FunctionEnterEvent, lambda e: (e.line, e.function)),
        )

    def test_loops(self):
        events = self._map([EventType.LOOP_BEGIN, EventType.LOOP_HIT], subject=self.LOOPS)
        self.assertEqual(
            [(5, 0)], _select(events, LoopBeginEvent, lambda e: (e.line, e.loop_id))
        )
        self.assertEqual(
            [(5, 0)], _select(events, LoopHitEvent, lambda e: (e.line, e.loop_id))
        )


class JavaFinderTest(unittest.TestCase):
    def test_function_finder(self):
        self.assertEqual(
            list(range(2, 19)),
            JavaFunctionFinder("test_java/Main.java", 2, "middle").get_locations(
                RESOURCES
            ),
        )
        self.assertEqual(
            [20, 21, 22, 23],
            JavaFunctionFinder("test_java/Main.java", 20, "main").get_locations(
                RESOURCES
            ),
        )

    def test_branch_finder(self):
        self.assertEqual(
            [4, 5, 6, 7, 8, 9, 10],
            JavaBranchFinder("test_java/Main.java", 4, True).get_locations(RESOURCES),
        )
        self.assertEqual(
            [4, 10, 11, 12, 13, 14, 15, 16],
            JavaBranchFinder("test_java/Main.java", 4, False).get_locations(RESOURCES),
        )

    def test_loop_finder(self):
        self.assertEqual(
            [5, 6, 7, 8],
            JavaLoopFinder("test_java_loops/Loops.java", 5).get_locations(RESOURCES),
        )


@unittest.skipUnless(HAVE_JDK, "no JDK (javac/java) available")
class JavaEndToEndTest(unittest.TestCase):
    """Instrument -> compile with jsflkit.jar -> run -> decode the trace."""

    @classmethod
    def setUpClass(cls):
        cls.jar = _ensure_jar()
        if cls.jar is None:
            raise unittest.SkipTest("could not obtain jsflkit.jar")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sflkit_java_e2e_")
        self.work = os.path.join(self.tmp, "work")
        self.mapping_path = os.path.join(self.tmp, "mapping.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, subject, main_class, events, thread_support=False):
        config = Config.create(
            path=os.path.join(RESOURCES, subject),
            language="java",
            events=",".join(e.name.lower() for e in events),
            working=self.work,
            mapping_path=self.mapping_path,
        )
        instrument_config(config)
        sources = glob.glob(os.path.join(self.work, "**", "*.java"), recursive=True)
        out_bin = os.path.join(self.tmp, "bin")
        os.makedirs(out_bin, exist_ok=True)
        compiled = subprocess.run(
            [JAVAC, "-cp", self.jar, "-d", out_bin] + sources,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, compiled.returncode, compiled.stderr)
        trace = os.path.join(self.tmp, "trace")
        subprocess.run(
            [JAVA, "-cp", os.pathsep.join([out_bin, self.jar]), main_class],
            cwd=out_bin,
            env={
                **os.environ,
                "EVENTS_PATH": trace,
                "EVENTS_THREADS": "1" if thread_support else "0",
            },
        )
        self.assertTrue(os.path.isfile(trace))
        base = EventMapping.load(config).mapping
        return eventlib.load(trace, base, with_thread_id=thread_support)

    def test_branches_def_use_conditions_decode(self):
        events = self._run(
            "test_java",
            "Main",
            [
                EventType.LINE,
                EventType.BRANCH,
                EventType.DEF,
                EventType.USE,
                EventType.CONDITION,
                EventType.FUNCTION_ENTER,
            ],
        )
        self.assertGreater(len(events), 0)
        # main + the two middle(...) calls all entered
        functions = [e.function for e in events if isinstance(e, FunctionEnterEvent)]
        self.assertEqual(1, functions.count("main"))
        self.assertEqual(2, functions.count("middle"))
        # the value of the parameters of the first call middle(3, 3, 5) is captured
        first_defs = {
            (e.var, e.value)
            for e in events
            if isinstance(e, DefEvent) and e.var in {"x", "y", "z"}
        }
        self.assertIn(("x", 3), first_defs)
        self.assertIn(("z", 5), first_defs)
        self.assertTrue(any(isinstance(e, ConditionEvent) for e in events))
        self.assertTrue(any(isinstance(e, BranchEvent) for e in events))

    def test_loop_decode_hit_count(self):
        events = self._run(
            "test_java_loops",
            "Loops",
            [
                EventType.LINE,
                EventType.BRANCH,
                EventType.DEF,
                EventType.USE,
                EventType.FUNCTION_ENTER,
                EventType.LOOP_BEGIN,
                EventType.LOOP_HIT,
            ],
        )
        # sum(4) iterates exactly four times
        self.assertEqual(1, sum(isinstance(e, LoopBeginEvent) for e in events))
        self.assertEqual(4, sum(isinstance(e, LoopHitEvent) for e in events))

    def test_for_loop_decode(self):
        # `for (int i = 0; i < n; ...)` is desugared into a while loop so that
        # the loop variable is in scope for the injected def/use/condition
        # events; sum(4) iterates four times and tests its condition five times.
        events = self._run(
            "test_java_for",
            "ForLoop",
            [
                EventType.LINE,
                EventType.BRANCH,
                EventType.DEF,
                EventType.USE,
                EventType.CONDITION,
                EventType.FUNCTION_ENTER,
                EventType.LOOP_BEGIN,
                EventType.LOOP_HIT,
            ],
        )
        self.assertEqual(4, sum(isinstance(e, LoopHitEvent) for e in events))
        self.assertEqual(5, sum(isinstance(e, ConditionEvent) for e in events))
        self.assertTrue(any(isinstance(e, DefEvent) and e.var == "i" for e in events))

    def test_all_event_types_decode(self):
        events = self._run(
            "test_java_all",
            "AllEv",
            [
                EventType.LINE,
                EventType.BRANCH,
                EventType.DEF,
                EventType.USE,
                EventType.CONDITION,
                EventType.FUNCTION_ENTER,
                EventType.FUNCTION_EXIT,
                EventType.FUNCTION_ERROR,
                EventType.LOOP_BEGIN,
                EventType.LOOP_HIT,
                EventType.LOOP_END,
                EventType.LEN,
            ],
        )
        present = {type(e).__name__ for e in events}
        for expected in (
            LineEvent, BranchEvent, DefEvent, UseEvent, ConditionEvent,
            FunctionEnterEvent, FunctionExitEvent, FunctionErrorEvent,
            LoopBeginEvent, LoopHitEvent, LoopEndEvent, LenEvent,
        ):
            self.assertIn(expected.__name__, present)
        # return values are captured; void methods report None
        exits = {(e.function, e.return_value) for e in events if isinstance(e, FunctionExitEvent)}
        self.assertIn(("pick", 2), exits)
        self.assertIn(("len", 5), exits)
        self.assertIn(("noop", None), exits)
        # the throwing method yields a function-error (and no exit)
        self.assertTrue(
            any(isinstance(e, FunctionErrorEvent) and e.function == "risky" for e in events)
        )

    def test_thread_ids(self):
        # With thread support, every event carries the writing thread's id, so a
        # multi-threaded run is split across the main thread and the two workers.
        events = self._run(
            "test_java_threads",
            "Threads",
            [EventType.LINE, EventType.FUNCTION_ENTER, EventType.LOOP_HIT],
            thread_support=True,
        )
        self.assertTrue(all(e.thread_id is not None for e in events))
        self.assertGreaterEqual(len({e.thread_id for e in events}), 2)


if __name__ == "__main__":
    unittest.main()
