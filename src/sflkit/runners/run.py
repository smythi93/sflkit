import abc
import enum
import os
import re
import shutil
import string
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

Environment = Dict[str, str]

PYTEST_COLLECT_PATTERN = re.compile(
    '<(?P<kind>Package|Module|Class|Function|UnitTestCase|TestCaseFunction) (?P<name>[^>]+|"([^"]|\\")+")>'
)
PYTEST_RESULT_PATTERN = re.compile(
    rb"= ((((?P<f>\d+) failed)|((?P<p>\d+) passed)|(\d+ warnings?))(, )?)+ in "
)

DEFAULT_TIMEOUT = 10


class PytestNode(abc.ABC):
    def __init__(self, name: str, parent=None, skip: bool = False):
        self.name = name
        self.parent: Optional[PytestNode] = parent
        self.children: List[PytestNode] = []
        self.skip = skip

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()

    @abc.abstractmethod
    def visit(self) -> List[Any]:
        pass


class Root(PytestNode):
    def visit(self) -> List[Any]:
        return sum([node.visit() for node in self.children], start=[])

    def __repr__(self):
        return self.name


class Package(PytestNode):
    def visit(self) -> List[Any]:
        return sum([node.visit() for node in self.children], start=[])

    def __repr__(self):
        if self.parent:
            if self.skip:
                return repr(self.parent)
            else:
                return os.path.join(repr(self.parent), self.name)
        else:
            return self.name


class Module(PytestNode):
    def visit(self) -> List[Any]:
        return sum([node.visit() for node in self.children], start=[])

    def __repr__(self):
        if self.parent:
            if self.skip:
                return repr(self.parent)
            else:
                return os.path.join(repr(self.parent), self.name)
        else:
            return self.name


class Class(PytestNode):
    def visit(self) -> List[Any]:
        return sum([node.visit() for node in self.children], start=[])

    def __repr__(self):
        if self.parent:
            return f"{repr(self.parent)}::{self.name}"
        else:
            return f"::{self.name}"


class Function(PytestNode):
    def visit(self) -> List[Any]:
        return [self] + sum([node.visit() for node in self.children], start=[])

    def __repr__(self):
        if self.parent:
            return f"{repr(self.parent)}::{self.name}"
        else:
            return f"::{self.name}"


def split(s: str, sep: str = ",", esc: str = "\"'"):
    values = list()
    current = ""
    escape = None
    for c in s:
        if c == escape:
            escape = None
        elif escape is None and c in esc:
            escape = c
        elif escape is None and c in sep:
            values.append(current)
            current = ""
            continue
        current += c
    values.append(current)
    return values


class PytestTree:
    def __init__(self, base: Optional[os.PathLike] = None):
        self.base = base
        self.roots: List[PytestNode] = []

    @staticmethod
    def _count_spaces(s: str):
        return len(s) - len(s.lstrip())

    @staticmethod
    def _clear_name(s: str):
        if (s.startswith('"') and s.endswith('"')) or (
            s.startswith("'") and s.endswith("'")
        ):
            s = s[1:-1].replace("\\\\", "\\")
        return s

    def parse(self, output: str, directory: Path = None, root_dir: Path = None):
        current_level = 0
        current_node = None
        if root_dir is not None:
            root_node = Root(str(root_dir))
            self.roots.append(root_node)
        else:
            root_node = None
        directory = None if directory is None else directory.absolute()
        first = True
        for line in output.split("\n"):
            if (
                root_dir is None
                and line.startswith("rootdir: ")
                and directory is not None
            ):
                root_dir = Path(split(line)[0].replace("rootdir: ", "")).absolute()
                current_node = Root(str(root_dir))
            match = PYTEST_COLLECT_PATTERN.search(line)
            if match:
                level = self._count_spaces(line) // 2
                name = self._clear_name(match.group("name"))
                skip = False
                if match.group("kind") == "Package":
                    node_class = Package
                    if (
                        first
                        and root_dir
                        and name == root_dir.parts[-1]
                        and not (root_dir / name).exists()
                    ):
                        skip = True
                    first = False
                    if not skip and directory:
                        name = str(root_dir / name)
                elif match.group("kind") == "Module":
                    node_class = Module
                    if (
                        first
                        and root_dir
                        and name == root_dir.parts[-1]
                        and not (root_dir / name).exists()
                    ):
                        skip = True
                    first = False
                    if not skip and directory:
                        name = str(root_dir / name)
                elif match.group("kind") in ("Class", "UnitTestCase"):
                    node_class = Class
                elif match.group("kind") in ("Function", "TestCaseFunction"):
                    node_class = Function
                else:
                    continue
                node = node_class(name, skip=skip)
                if level == 0:
                    current_node = node
                    current_level = 0
                    if root_node:
                        node.parent = root_node
                        root_node.children.append(node)
                    else:
                        self.roots.append(node)
                elif level > current_level:
                    current_node.children.append(node)
                    node.parent = current_node
                    current_node = node
                    current_level = level
                else:
                    for _ in range(current_level - level + 1):
                        if current_node.parent:
                            current_node = current_node.parent
                        else:
                            current_node = root_node
                    current_node.children.append(node)
                    node.parent = current_node
                    current_node = node
                    current_level = level

    def visit(self):
        return sum([node.visit() for node in self.roots], start=[])


class TestResult(enum.Enum):
    PASSING = "PASSING"
    FAILING = "FAILING"
    UNDEFINED = "UNDEFINED"

    def get_dir(self):
        return self.value.lower()


class Runner(abc.ABC):
    def __init__(self, re_filter: str = r".*", timeout=DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.re_filter = re.compile(re_filter)

    def get_tests(
        self,
        directory: Path,
        base: Optional[os.PathLike] = None,
        environ: Environment = None,
    ) -> List[str]:
        return []

    def run_test(
        self, directory: Path, test: str, environ: Environment = None
    ) -> TestResult:
        return TestResult.UNDEFINED

    def filter_tests(self, tests: List[str]) -> List[str]:
        return list(filter(self.re_filter.search, tests))

    @staticmethod
    def safe(s: str):
        for c in string.punctuation:
            if c in s:
                s = s.replace(c, "_")
        return s

    def run_tests(
        self,
        directory: Path,
        output: Path,
        tests: List[str],
        environ: Environment = None,
    ):
        output.mkdir(parents=True, exist_ok=True)
        for test_result in TestResult:
            (output / test_result.get_dir()).mkdir(parents=True, exist_ok=True)
        for run_id, test in enumerate(tests):
            test_result = self.run_test(directory, test, environ=environ)
            if os.path.exists(directory / "EVENTS_PATH"):
                shutil.move(
                    directory / "EVENTS_PATH",
                    output / test_result.get_dir() / self.safe(test),
                )

    def run(
        self,
        directory: Path,
        output: Path,
        base: Optional[os.PathLike] = None,
        environ: Environment = None,
    ):
        self.run_tests(
            directory,
            output,
            self.filter_tests(self.get_tests(directory, base=base, environ=environ)),
            environ=environ,
        )


class VoidRunner(Runner):
    pass


class PytestRunner(Runner):
    def get_tests(
        self,
        directory: Path,
        base: Optional[os.PathLike] = None,
        environ: Environment = None,
    ) -> List[str]:
        c = []
        if base:
            c.append(base)
            root_dir = directory / base
        else:
            root_dir = None
        output = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "--collect-only",
            ]
            + c,
            stdout=subprocess.PIPE,
            env=environ,
            cwd=directory,
        ).stdout.decode("utf-8")
        tree = PytestTree()
        tree.parse(output, directory=directory, root_dir=root_dir)
        return list(map(str, tree.visit()))

    @staticmethod
    def __get_pytest_result__(
        output: bytes,
    ) -> tuple[bool, Optional[int], Optional[int]]:
        match = PYTEST_RESULT_PATTERN.search(output)
        if match:
            if match.group("f"):
                failing = int(match.group("f"))
            else:
                failing = 0
            if match.group("p"):
                passing = int(match.group("p"))
            else:
                passing = 0
            return True, passing, failing
        return False, None, None

    def run_test(
        self, directory: Path, test: str, environ: Environment = None
    ) -> TestResult:
        try:
            output = subprocess.run(
                ["python", "-m", "pytest", test],
                stdout=subprocess.PIPE,
                env=environ,
                cwd=directory,
                timeout=self.timeout,
            ).stdout
        except subprocess.TimeoutExpired:
            return TestResult.UNDEFINED
        successful, passing, failing = self.__get_pytest_result__(output)
        if successful:
            if passing > 0 and failing == 0:
                return TestResult.PASSING
            elif failing > 0 and passing == 0:
                return TestResult.FAILING
            else:
                return TestResult.UNDEFINED
        else:
            return TestResult.UNDEFINED


class UnittestRunner(Runner):
    pass


class InputRunner(Runner):
    def __init__(
        self,
        access: os.PathLike,
        passing: List[str | List[str]],
        failing: List[str | List[str]],
    ):
        super().__init__()
        self.access = access
        self.passing: Dict[str, List[str]] = self._prepare_tests(passing, "passing")
        self.failing: Dict[str, List[str]] = self._prepare_tests(failing, "failing")
        self.output: Dict[str, Tuple[str, str]] = dict()

    @staticmethod
    def _prepare_tests(tests: List[str | List[str]], prefix: str):
        return {
            f"{prefix}_{i}": (test if isinstance(test, list) else test.split("\n"))
            for i, test in enumerate(tests)
        }

    def get_tests(
        self,
        directory: Path,
        base: Optional[os.PathLike] = None,
        environ: Environment = None,
    ) -> List[str]:
        return list(self.passing.keys()) + list(self.failing.keys())

    def run_test(
        self, directory: Path, test_name: str, environ: Environment = None
    ) -> TestResult:
        if "passing" in test_name:
            test = self.passing[test_name]
            result = TestResult.PASSING
        else:
            test = self.failing[test_name]
            result = TestResult.FAILING
        try:
            process = subprocess.run(
                ["python", self.access] + test,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environ,
                cwd=directory,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return TestResult.UNDEFINED
        self.output[test_name] = (
            process.stdout.decode("utf8"),
            process.stderr.decode("utf8"),
        )
        return result
