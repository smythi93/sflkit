import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from sflkit import Config, instrument_config, Analyzer
from sflkit.analysis.analysis_type import AnalysisType
from sflkit.analysis.suggestion import Location
from sflkit.events.mapping import EventMapping
from sflkit.events.event_file import EventFile
from sflkit.runners.run import (
    PytestRunner,
    InputRunner,
    PytestStructure,
)
from utils import BaseTest


class RunnerTests(BaseTest):
    PYTEST_COLLECT = (
        "tests/1.py::test_1\n"
        "tests/1.py::test_2\n"
        "tests/1/2.py::test_3\n"
        "tests/1/2.py::test_4\n"
        "tests/1/3.py::test_5\n"
        "\n"
        "5 tests collected in 0.01s"
    )

    def assertPathExists(self, path: os.PathLike):
        self.assertTrue(os.path.exists(path), f"{path} does not exists.")

    def test_runner(self):
        config = Config.create(
            path=os.path.join(self.TEST_RESOURCES, BaseTest.TEST_RUNNER),
            language="python",
            events="line",
            predicates="line",
            working=BaseTest.TEST_DIR,
            exclude="tests",
            mapping_path=BaseTest.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(
            Path(BaseTest.TEST_DIR), output, files=[Path("tests", "test_middle.py")]
        )
        self.assertPathExists(output)
        self.assertPathExists(output / "passing")
        self.assertPathExists(output / "failing")
        self.assertPathExists(output / "undefined")
        mapping = EventMapping.load(config)
        analyzer = Analyzer(
            [
                EventFile(
                    output / "failing" / os.listdir(output / "failing")[0],
                    0,
                    mapping,
                    failing=True,
                )
            ],
            [
                EventFile(output / "passing" / path, run_id, mapping)
                for run_id, path in enumerate(os.listdir(output / "passing"), start=1)
            ],
            config.factory,
        )
        analyzer.analyze()
        predicates = analyzer.get_analysis_by_type(AnalysisType.LINE)
        suggestions = sorted(map(lambda p: p.get_suggestion(), predicates))
        self.assertEqual(1, suggestions[-1].suspiciousness)
        self.assertEqual(1, len(suggestions[-1].lines))
        self.assertEqual(Location("middle.py", 7), suggestions[-1].lines[0])

    def test_input_runner(self):
        config = Config.create(
            path=os.path.join(self.TEST_RESOURCES, BaseTest.TEST_SUGGESTIONS),
            language="python",
            events="line",
            predicates="line",
            working=BaseTest.TEST_DIR,
            exclude="tests",
            mapping_path=BaseTest.TEST_MAPPING,
        )
        instrument_config(config)
        runner = InputRunner(
            "main.py",
            failing=[["2", "1", "3"]],
            passing=[["3", "2", "1"], ["3", "1", "2"]],
        )
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output)
        self.assertPathExists(output)
        self.assertPathExists(output / "passing")
        self.assertPathExists(output / "failing")
        self.assertPathExists(output / "undefined")
        mapping = EventMapping.load(config)
        analyzer = Analyzer(
            [
                EventFile(
                    output / "failing" / os.listdir(output / "failing")[0],
                    0,
                    mapping,
                    failing=True,
                )
            ],
            [
                EventFile(output / "passing" / path, run_id, mapping)
                for run_id, path in enumerate(os.listdir(output / "passing"), start=1)
            ],
            config.factory,
        )
        analyzer.analyze()
        predicates = analyzer.get_analysis_by_type(AnalysisType.LINE)
        suggestions = sorted(map(lambda p: p.get_suggestion(), predicates))
        self.assertEqual(1, suggestions[-1].suspiciousness)
        self.assertEqual(1, len(suggestions[-1].lines))
        self.assertEqual(Location("main.py", 10), suggestions[-1].lines[0])

    def test_parse_and_paths(self):
        collect = (
            "\n"
            "<Package b>\n"
            "  <Module test_b.py>\n"
            "    <Function test_d>\n"
            "<Package tests>\n"
            "  <Module test_a.py>\n"
            "    <Function test_a>\n"
            "    <Function test_b>\n"
            "    <Function test_c>\n"
        )
        tests = PytestStructure.parse_tests(collect)
        self.assertEqual(4, len(tests))
        self.assertIn(os.path.join("b", "test_b.py::test_d"), tests)
        self.assertIn(os.path.join("tests", "test_a.py::test_a"), tests)
        self.assertIn(os.path.join("tests", "test_a.py::test_b"), tests)
        self.assertIn(os.path.join("tests", "test_a.py::test_c"), tests)
        files = PytestRunner.get_files(
            [
                Path("structure", "tests", "b", "test_b.py"),
                Path("structure", "tests", "test_a.py::test_a"),
                Path("structure", "tests", "test_a.py::test_b"),
                Path("structure", "tests", "test_a.py::test_c"),
            ]
        )
        self.assertEqual(2, len(files))
        self.assertIn(os.path.join("structure", "tests", "b", "test_b.py"), files)
        self.assertIn(os.path.join("structure", "tests", "test_a.py"), files)
        directory = Path(BaseTest.TEST_RESOURCES, "structure")
        files = PytestRunner.get_absolute_files(
            files,
            directory,
        )
        self.assertEqual(2, len(files))
        self.assertIn(
            directory / "structure" / "tests" / "b" / "test_b.py",
            files,
        )
        self.assertIn(directory / "structure" / "tests" / "test_a.py", files)
        tests = PytestRunner.normalize_paths(
            tests,
            files=files,
            directory=directory,
            root_dir=directory / "structure" / "tests",
        )
        self.assertEqual(4, len(tests))
        self.assertIn(
            os.path.join("structure", "tests", "b", "test_b.py::test_d"),
            tests,
        )
        self.assertIn(
            os.path.join("structure", "tests", "test_a.py::test_a"),
            tests,
        )
        self.assertIn(
            os.path.join("structure", "tests", "test_a.py::test_b"),
            tests,
        )
        self.assertIn(
            os.path.join("structure", "tests", "test_a.py::test_c"),
            tests,
        )

    def test_runner_python_interpreter(self):
        """
        Test that the python argument is correctly passed to subprocess calls.
        This test verifies that pytest collection uses the specified python
        interpreter instead of the default 'python3'.
        """
        custom_python = "python3.11"

        # Create a mock for subprocess.run
        with patch("sflkit.runners.run.subprocess.run") as mock_run:
            # Create a mock return value that simulates pytest collection output
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.stdout = (
                b"<Package tests>\n"
                b"  <Module test_a.py>\n"
                b"    <Function test_sample>\n"
            )
            mock_process.stderr = b""
            mock_run.return_value = mock_process

            # Create a pytest runner
            runner = PytestRunner(set_python_path=True)

            # Create a temporary directory for testing
            test_dir = Path(BaseTest.TEST_DIR)
            output_dir = test_dir / "events_python_test"

            # Call runner.run with custom python interpreter
            runner.run(
                test_dir,
                output_dir,
                python=custom_python,
            )

            # Verify that subprocess.run was called
            self.assertTrue(mock_run.called, "subprocess.run should have been called")

            # Collect all the calls made to subprocess.run
            calls = mock_run.call_args_list
            self.assertGreater(
                len(calls), 0, "Expected at least one call to subprocess.run"
            )

            # Check that the first call (pytest collection) uses the custom python interpreter
            first_call_args = calls[0][0][0]  # Get the command list from the first call
            self.assertIsInstance(first_call_args, list, "Command should be a list")
            self.assertEqual(
                first_call_args[0],
                custom_python,
                f"First subprocess call should start with {custom_python}, got {first_call_args[0]}",
            )
            self.assertIn(
                "-m",
                first_call_args,
                "pytest collection call should contain -m argument",
            )
            self.assertIn(
                "pytest",
                first_call_args,
                "pytest collection call should contain pytest argument",
            )
            self.assertIn(
                "--collect-only",
                first_call_args,
                "pytest collection call should contain --collect-only argument",
            )
