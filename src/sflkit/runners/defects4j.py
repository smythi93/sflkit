"""A runner that collects sflkit event traces from Defects4J bugs.

The flow for a single bug is:

    checkout (buggy) -> defects4j compile -> instrument the source classes
    (per file, falling back to the original on failure) -> recompile the
    instrumented classes over target/classes (reverting any file whose
    instrumentation does not compile) -> run every relevant test method in its
    own JVM, capturing one event trace per test, and classify pass/fail.

The output mirrors the layout the rest of sflkit expects: a mapping file plus
``passing``/``failing``/``undefined`` directories of event traces, ready for
``EventMapping``/``Analyzer``.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from sflkit.language.language import Language
from sflkit.language.meta import CombinationVisitor, IDGenerator, TmpGenerator
from sflkit.logger import LOGGER
from sflkit.runners.run import Runner, TestResult
from sflkitlib.events import EventType
from sflkitlib.events.event import EventEncoder

DEFAULT_EVENTS = [
    EventType.LINE,
    EventType.BRANCH,
    EventType.FUNCTION_ENTER,
    EventType.LOOP_BEGIN,
    EventType.LOOP_HIT,
]

_JAVAC_ERROR = re.compile(r"^(?P<file>/[^:\n]+\.java):\d+: error:", re.MULTILINE)
_RESOURCE = Path(__file__).parent / "resources" / "SflkitTestRunner.java"


class Defects4JError(Exception):
    pass


class Defects4J:
    """Thin wrapper around the ``defects4j`` command-line tool."""

    def __init__(
        self,
        defects4j_home: Optional[os.PathLike] = None,
        java_home: Optional[os.PathLike] = None,
    ):
        home = defects4j_home or os.environ.get("DEFECTS4J_HOME")
        self.home = Path(home) if home else Path.home() / "defects4j"
        self.bin = self.home / "framework" / "bin" / "defects4j"
        if not self.bin.exists():
            raise Defects4JError(f"defects4j not found at {self.bin}")
        # Recent Defects4J requires Java 11; allow overriding via env.
        java = (
            java_home
            or os.environ.get("DEFECTS4J_JAVA_HOME")
            or (Path.home() / ".jenv" / "versions" / "11")
        )
        self.java_home = Path(java)
        self.env = os.environ.copy()
        self.env["JAVA_HOME"] = str(self.java_home)
        self.env["PATH"] = os.pathsep.join(
            [str(self.bin.parent), str(self.java_home / "bin"), self.env.get("PATH", "")]
        )

    @property
    def javac(self) -> str:
        return str(self.java_home / "bin" / "javac")

    @property
    def java(self) -> str:
        return str(self.java_home / "bin" / "java")

    def _run(self, *args, cwd: Optional[os.PathLike] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(self.bin), *args],
            cwd=str(cwd) if cwd else None,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def checkout(self, project: str, bug: int, workdir: os.PathLike, buggy: bool = True):
        if Path(workdir).exists():
            shutil.rmtree(workdir)
        version = f"{bug}{'b' if buggy else 'f'}"
        result = self._run("checkout", "-p", project, "-v", version, "-w", str(workdir))
        if result.returncode:
            raise Defects4JError(result.stderr or result.stdout)

    def compile(self, workdir: os.PathLike):
        result = self._run("compile", cwd=workdir)
        if result.returncode:
            raise Defects4JError(result.stderr or result.stdout)

    def export(self, prop: str, workdir: os.PathLike) -> str:
        result = self._run("export", "-p", prop, cwd=workdir)
        if result.returncode:
            raise Defects4JError(result.stderr or result.stdout)
        return result.stdout.strip()


def instrument_directory(
    language: Language,
    events: List[EventType],
    src_root: os.PathLike,
    dst_root: os.PathLike,
    mapping_path: os.PathLike,
):
    """Instrument every source file under ``src_root`` into ``dst_root``.

    Files that fail to parse/instrument are copied unmodified, so the build can
    proceed even where jast cannot yet handle a file.  Returns (instrumented,
    copied, events).
    """
    language.setup()
    meta_visitor = CombinationVisitor(
        language,
        IDGenerator(),
        IDGenerator(),
        TmpGenerator(),
        [language.meta_visitors[e] for e in events],
    )
    visitor = language.visitor(meta_visitor)
    instrumented = copied = 0
    for dirpath, _, filenames in os.walk(src_root):
        for filename in filenames:
            source = os.path.join(dirpath, filename)
            relative = os.path.relpath(source, src_root)
            target = os.path.join(dst_root, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if any(filename.endswith(f".{suffix}") for suffix in language.suffixes):
                try:
                    visitor.instrument(source, target, file=relative)
                    instrumented += 1
                except Exception as error:  # noqa: BLE001 - fall back to original
                    LOGGER.debug(f"Could not instrument {relative}: {error}")
                    shutil.copy(source, target)
                    copied += 1
            else:
                shutil.copy(source, target)
    with open(mapping_path, "w") as fp:
        json.dump(visitor.events, fp, cls=EventEncoder)
    LOGGER.info(
        f"Instrumented {instrumented} files ({copied} copied) "
        f"with {len(visitor.events)} events"
    )
    return instrumented, copied, visitor.events


class Defects4JRunner(Runner):
    """Collect event traces for a Defects4J bug into passing/failing dirs."""

    def __init__(
        self,
        jlib_jar: os.PathLike,
        defects4j: Optional[Defects4J] = None,
        events: Optional[List[EventType]] = None,
        timeout: int = 300,
        max_compile_retries: int = 50,
    ):
        super().__init__(timeout=timeout)
        self.jlib_jar = str(jlib_jar)
        self.defects4j = defects4j or Defects4J()
        self.events = events or list(DEFAULT_EVENTS)
        self.max_compile_retries = max_compile_retries
        # populated by setup()
        self.workdir: Optional[Path] = None
        self.run_classpath: Optional[str] = None
        self.mapping_path: Optional[Path] = None

    def collect(
        self,
        project: str,
        bug: int,
        output: os.PathLike,
        workdir: Optional[os.PathLike] = None,
        mapping_path: Optional[os.PathLike] = None,
        tests: Optional[List[str]] = None,
    ) -> Dict[TestResult, set]:
        """Run the full pipeline for one bug and return the test partition."""
        workdir = Path(workdir or tempfile.mkdtemp(prefix=f"d4j_{project}_{bug}_"))
        output = Path(output)
        mapping_path = Path(mapping_path or output / "mapping.json")
        output.mkdir(parents=True, exist_ok=True)

        d4j = self.defects4j
        LOGGER.info(f"Checking out {project}-{bug}b into {workdir}")
        d4j.checkout(project, bug, workdir)
        d4j.compile(workdir)

        src_classes = workdir / d4j.export("dir.src.classes", workdir)
        cp_compile = d4j.export("cp.compile", workdir)
        cp_test = d4j.export("cp.test", workdir)
        bin_classes = workdir / d4j.export("dir.bin.classes", workdir)

        # instrument source classes (with per-file fallback)
        instrumented_src = workdir / ".sflkit_instrumented_src"
        if instrumented_src.exists():
            shutil.rmtree(instrumented_src)
        instrument_directory(
            Language.JAVA, self.events, src_classes, instrumented_src, mapping_path
        )

        # recompile the instrumented sources over bin.classes, reverting any
        # file whose instrumentation does not compile
        self._recompile(instrumented_src, src_classes, bin_classes, cp_compile)

        # compile the JUnit launcher against the test classpath
        runner_dir = workdir / ".sflkit_runner"
        runner_dir.mkdir(exist_ok=True)
        self._compile_runner(cp_test, runner_dir)

        self.workdir = workdir
        self.mapping_path = mapping_path
        self.run_classpath = os.pathsep.join([cp_test, str(runner_dir), self.jlib_jar])

        if tests is None:
            tests = self._collect_tests(project, workdir)
        LOGGER.info(f"Running {len(tests)} tests for {project}-{bug}b")
        self.run_tests(workdir, output, tests)
        return self.tests

    # ----- pipeline steps -------------------------------------------------

    def _recompile(self, instrumented_src, original_src, out_dir, cp_compile):
        sources = self._java_files(instrumented_src)
        reverted_total = 0
        for _ in range(self.max_compile_retries):
            result = subprocess.run(
                [
                    self.defects4j.javac,
                    "-encoding", "UTF-8", "-nowarn",
                    "-cp", os.pathsep.join([cp_compile, self.jlib_jar]),
                    "-d", str(out_dir),
                    *sources,
                ],
                env=self.defects4j.env,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                if reverted_total:
                    LOGGER.info(
                        f"Reverted {reverted_total} file(s) whose instrumentation "
                        f"did not compile"
                    )
                return
            bad_files = set(_JAVAC_ERROR.findall(result.stderr))
            reverted = False
            for bad in bad_files:
                relative = os.path.relpath(bad, instrumented_src)
                original = os.path.join(original_src, relative)
                if os.path.exists(original) and not _same_file(bad, original):
                    shutil.copy(original, bad)
                    reverted = True
                    reverted_total += 1
            if not reverted:
                raise Defects4JError(
                    f"Could not compile instrumented sources:\n{result.stderr}"
                )
        raise Defects4JError("Exceeded compile retries while reverting files")

    def _compile_runner(self, cp_test, runner_dir):
        result = subprocess.run(
            [self.defects4j.javac, "-cp", cp_test, "-d", str(runner_dir), str(_RESOURCE)],
            env=self.defects4j.env,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise Defects4JError(f"Could not compile test runner:\n{result.stderr}")

    def _collect_tests(self, project, workdir) -> List[str]:
        trigger = [
            t for t in self.defects4j.export("tests.trigger", workdir).splitlines() if t
        ]
        relevant_classes = [
            c
            for c in self.defects4j.export("tests.relevant", workdir).splitlines()
            if c
        ]
        methods: List[str] = list(trigger)
        seen = set(trigger)
        for test_class in relevant_classes:
            for method in self._list_methods(test_class):
                if method not in seen:
                    seen.add(method)
                    methods.append(method)
        return methods

    def _list_methods(self, test_class: str) -> List[str]:
        result = subprocess.run(
            [self.defects4j.java, "-cp", self.run_classpath, "SflkitTestRunner",
             "list", test_class],
            env=self.defects4j.env,
            capture_output=True,
            text=True,
        )
        return [line for line in result.stdout.splitlines() if "#" in line]

    # ----- Runner interface ----------------------------------------------

    def get_tests(self, directory, files=None, base=None, environ=None, python=None, k=None):
        return self._collect_tests(None, directory)

    def run_test(self, directory, test, environ=None, python=None) -> TestResult:
        environ = dict(environ or self.defects4j.env)
        # Let JLib write to <directory>/EVENTS_PATH, which run_tests then moves.
        environ.pop("EVENTS_PATH", None)
        try:
            result = subprocess.run(
                [self.defects4j.java, "-cp", self.run_classpath, "SflkitTestRunner",
                 "run", test],
                cwd=str(directory),
                env=environ,
                capture_output=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return TestResult.UNDEFINED
        if result.returncode == 0:
            return TestResult.PASSING
        if result.returncode == 1:
            return TestResult.FAILING
        return TestResult.UNDEFINED

    @staticmethod
    def _java_files(root) -> List[str]:
        return [
            os.path.join(dp, f)
            for dp, _, fs in os.walk(root)
            for f in fs
            if f.endswith(".java")
        ]


def _same_file(a, b) -> bool:
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False
