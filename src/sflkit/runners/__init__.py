import enum

from sflkit.runners.run import (
    Runner,
    VoidRunner,
    PytestRunner,
    UnittestRunner,
    InputRunner,
    ParallelPytestRunner,
    OnlinePytestRunner,
)


class RunnerType(enum.Enum):
    def __init__(self, runner: Runner):
        self.runner = runner

    VOID_RUNNER = VoidRunner
    PYTEST_RUNNER = PytestRunner
    UNITTEST_RUNNER = UnittestRunner
    INPUT_RUNNER = InputRunner
    PARALLEL_PYTEST_RUNNER = ParallelPytestRunner
    PARALLEL_UNITTEST_RUNNER = UnittestRunner
    ONLINE_PYTEST_RUNNER = OnlinePytestRunner
    PARALLEL_ONLINE_PYTEST_RUNNER = OnlinePytestRunner
