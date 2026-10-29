"""
pytest plugin that builds an artifact per test instead of a trace.

Loaded with ``-p sflkit.online.plugin`` and configured entirely through the
environment, because the runner starts pytest in a subprocess and the plugin
has to configure itself before any test runs.

One tracer serves the whole pytest process and one artifact is written per
test, named and filed exactly where the offline runner would have put that
test's trace. A process may therefore run the entire suite and still produce
per-test evidence, which is what makes it possible to drop the
process-per-test model later without changing anything downstream.

Environment:

``SFLKIT_ONLINE_MAPPING``
    Path to the event mapping written by instrumentation. Required.
``SFLKIT_ONLINE_ROOT``
    Directory the mapping's file names are relative to. Required.
``SFLKIT_ONLINE_OUTPUT``
    Directory to write artifacts into, under ``passing``/``failing``/
    ``undefined``. Required.
``SFLKIT_ONLINE_THREADS``
    ``1`` to trace threads and stamp events with a thread id.
``SFLKIT_ONLINE_TREE``
    ``0`` to skip building the call tree.
"""

import os
from pathlib import Path
from typing import Dict, Optional

from sflkit.events.mapping import EventMapping
from sflkit.logger import LOGGER
from sflkit.online.session import OnlineSession
from sflkit.online.tracer import LocationIndex
from sflkit.runners.run import Runner, TestResult

#: Environment variable holding the event mapping path.
MAPPING = "SFLKIT_ONLINE_MAPPING"
#: Environment variable holding the subject root.
ROOT = "SFLKIT_ONLINE_ROOT"
#: Environment variable holding the artifact output directory.
OUTPUT = "SFLKIT_ONLINE_OUTPUT"
#: Environment variable enabling thread support.
THREADS = "SFLKIT_ONLINE_THREADS"
#: Environment variable disabling tree construction.
TREE = "SFLKIT_ONLINE_TREE"


def _flag(name: str, default: bool) -> bool:
    """
    :param name: Environment variable to read.
    :param default: Value to use when it is unset.
    :returns: The variable read as a boolean.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "t", "y")


class OnlineCollector:
    """
    Traces each test and writes its artifact.

    :ivar index: Location index, built once and shared by every test.
    :ivar output: Where artifacts are written.
    :ivar session: The session tracing the test currently running.
    :ivar results: Verdict per test id, filled in as reports come in.
    """

    def __init__(
        self, index: LocationIndex, output: Path, thread_support: bool, tree: bool
    ):
        """
        :param index: Location index for the subject.
        :param output: Directory to write artifacts into.
        :param thread_support: Trace threads.
        :param tree: Build the call tree.
        """
        self.index = index
        self.output = output
        self.thread_support = thread_support
        self.tree = tree
        self.session: Optional[OnlineSession] = None
        self.results: Dict[str, TestResult] = dict()
        self._run_id = 0

    def start(self, test: str) -> None:
        """
        Begin tracing *test*.

        :param test: The test's node id.
        """
        # A fresh session per test keeps each artifact independent, which is
        # what lets the parent merge them in any order it likes. The index is
        # shared because building it parses every source file.
        self.session = OnlineSession(
            index=self.index,
            thread_support=self.thread_support,
            tree=self.tree,
        )
        self.session.start(test, failing=None, run_id=self._run_id)
        self._run_id += 1

    def stop(self, test: str) -> None:
        """
        Finish *test* and write its artifact.

        :param test: The test's node id.
        """
        if self.session is None:
            return
        session, self.session = self.session, None
        try:
            session.stop()
        except Exception:
            LOGGER.exception("Could not stop tracing %s", test)
            return
        result = self.results.get(test, TestResult.UNDEFINED)
        artifact = session.artifact()
        artifact.result = result
        directory = self.output / result.get_dir()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            artifact.dump(directory / Runner.safe(test))
        except OSError:
            LOGGER.exception("Could not write the artifact for %s", test)


_collector: Optional[OnlineCollector] = None


def pytest_configure(config):
    """Build the shared index once, before any test runs."""
    global _collector
    mapping_path = os.environ.get(MAPPING)
    root = os.environ.get(ROOT)
    output = os.environ.get(OUTPUT)
    if not (mapping_path and root and output):
        LOGGER.warning(
            "sflkit online plugin loaded without %s, %s and %s; not tracing",
            MAPPING,
            ROOT,
            OUTPUT,
        )
        return
    try:
        mapping = EventMapping.load_from_file(Path(mapping_path), root)
        _collector = OnlineCollector(
            LocationIndex(mapping, root),
            Path(output),
            _flag(THREADS, False),
            _flag(TREE, True),
        )
    except Exception:
        # Collecting must never be the reason a test suite fails to run: a
        # misconfigured collector costs evidence, not the run.
        LOGGER.exception("Could not set up online collection; not tracing")
        _collector = None


def pytest_runtest_setup(item):
    """Start tracing before the test body runs."""
    if _collector is not None:
        _collector.start(item.nodeid)


def pytest_runtest_logreport(report):
    """
    Record the verdict of the test body.

    Only the call phase decides pass or fail; a failure during setup or
    teardown leaves the verdict undefined, which is what it is.
    """
    if _collector is None or report.when != "call":
        return
    _collector.results[report.nodeid] = (
        TestResult.PASSING if report.passed else TestResult.FAILING
    )


def pytest_runtest_teardown(item, nextitem):
    """Stop tracing and write the artifact."""
    if _collector is not None:
        _collector.stop(item.nodeid)
