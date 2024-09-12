import os
from pathlib import Path

from sflkit import Config, instrument_config
from sflkit.analysis.analysis_type import AnalysisType
from sflkit.analysis.suggestion import Location
from sflkit.weights.analyzer import TimeAnalyzer
from sflkit.weights.models import (
    TestLineModel,
    TestDefUseModel,
    TestFunctionModel,
    TestDefUsesModel,
    TestAssertDefUseModel,
    TestAssertDefUsesModel,
    WeightedAnalyses,
)
from sflkit.events.event_file import EventFile
from sflkit.events.mapping import EventMapping
from sflkit.runners import PytestRunner
from utils import BaseTest


class TestTimeWeights(BaseTest):
    def test_time_function(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_WEIGHTS_SETUP)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line,test_start,test_end",
            working=BaseTest.TEST_DIR,
            exclude="test.py",
            test_files="test.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        analyzer = TimeAnalyzer(
            TestFunctionModel,
            [
                EventFile(
                    output / "failing" / path,
                    run_id,
                    mapping,
                    True,
                )
                for run_id, path in enumerate(os.listdir(output / "failing"))
            ],
            [],
            config.factory,
        )
        analyzer.analyze()
        suggestions = analyzer.get_sorted_suggestions(src, type_=AnalysisType.LINE)
        self.assertEqual(2, len(suggestions))
        self.assertAlmostEquals(1, suggestions[0].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.5, suggestions[1].suspiciousness, delta=0.00001)
        self.assertEqual(1, len(suggestions[0].lines))
        self.assertIn(Location("main.py", 10), suggestions[0].lines)
        self.assertEqual(2, len(suggestions[1].lines))
        self.assertIn(Location("main.py", 6), suggestions[1].lines)
        self.assertIn(Location("main.py", 2), suggestions[1].lines)

    def test_time_line(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_WEIGHTS_LINES)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line",
            working=BaseTest.TEST_DIR,
            exclude="test.py",
            test_files="test.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        analyzer = TimeAnalyzer(
            TestLineModel,
            [
                EventFile(
                    output / "failing" / path,
                    run_id,
                    mapping,
                    True,
                )
                for run_id, path in enumerate(os.listdir(output / "failing"))
            ],
            [
                EventFile(output / "passing" / path, run_id, mapping)
                for run_id, path in enumerate(os.listdir(output / "passing"), start=2)
            ],
            config.factory,
        )
        analyzer.analyze()
        suggestions = analyzer.get_sorted_suggestions(src, type_=AnalysisType.LINE)
        self.assertEqual(3, len(suggestions))
        self.assertAlmostEquals(1, suggestions[0].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.775, suggestions[1].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.3, suggestions[2].suspiciousness, delta=0.00001)
        self.assertEqual(1, len(suggestions[0].lines))
        self.assertIn(Location("main.py", 10), suggestions[0].lines)
        self.assertEqual(1, len(suggestions[1].lines))
        self.assertIn(Location("main.py", 6), suggestions[1].lines)
        self.assertEqual(1, len(suggestions[2].lines))
        self.assertIn(Location("main.py", 2), suggestions[2].lines)

    def test_time_def_use(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_WEIGHTS_DEF_USE)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line,test_def,test_use",
            working=BaseTest.TEST_DIR,
            exclude="test.py",
            test_files="test.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        analyzer = TimeAnalyzer(
            TestDefUseModel,
            [
                EventFile(
                    output / "failing" / path,
                    run_id,
                    mapping,
                    True,
                )
                for run_id, path in enumerate(os.listdir(output / "failing"))
            ],
            [
                EventFile(output / "passing" / path, run_id, mapping)
                for run_id, path in enumerate(os.listdir(output / "passing"), start=2)
            ],
            config.factory,
        )
        analyzer.analyze()
        suggestions = analyzer.get_sorted_suggestions(src, type_=AnalysisType.LINE)
        self.assertEqual(3, len(suggestions))
        self.assertAlmostEquals(0.85416, suggestions[0].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.64583, suggestions[1].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.4375, suggestions[2].suspiciousness, delta=0.00001)
        self.assertEqual(1, len(suggestions[0].lines))
        self.assertIn(Location("main.py", 10), suggestions[0].lines)
        self.assertEqual(1, len(suggestions[1].lines))
        self.assertIn(Location("main.py", 6), suggestions[1].lines)
        self.assertEqual(1, len(suggestions[2].lines))
        self.assertIn(Location("main.py", 2), suggestions[2].lines)

    def test_time_def_uses(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_WEIGHTS_DEF_USES)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line,test_def,test_use",
            working=BaseTest.TEST_DIR,
            exclude="test.py",
            test_files="test.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        analyzer = TimeAnalyzer(
            TestDefUsesModel,
            [
                EventFile(
                    output / "failing" / path,
                    run_id,
                    mapping,
                    True,
                )
                for run_id, path in enumerate(os.listdir(output / "failing"))
            ],
            [
                EventFile(output / "passing" / path, run_id, mapping)
                for run_id, path in enumerate(os.listdir(output / "passing"), start=2)
            ],
            config.factory,
        )
        analyzer.analyze()
        suggestions = analyzer.get_sorted_suggestions(src, type_=AnalysisType.LINE)
        self.assertEqual(3, len(suggestions))
        self.assertAlmostEquals(0.80555, suggestions[0].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.61111, suggestions[1].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.38888, suggestions[2].suspiciousness, delta=0.00001)
        self.assertEqual(1, len(suggestions[0].lines))
        self.assertIn(Location("main.py", 10), suggestions[0].lines)
        self.assertEqual(1, len(suggestions[1].lines))
        self.assertIn(Location("main.py", 6), suggestions[1].lines)
        self.assertEqual(1, len(suggestions[2].lines))
        self.assertIn(Location("main.py", 2), suggestions[2].lines)

    def test_time_assert_def_use(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_WEIGHTS_DEF_USE)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line,test_def,test_use,test_assert",
            working=BaseTest.TEST_DIR,
            tests=r"test\.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        analyzer = TimeAnalyzer(
            TestAssertDefUseModel,
            [
                EventFile(
                    output / "failing" / path,
                    run_id,
                    mapping,
                    True,
                )
                for run_id, path in enumerate(os.listdir(output / "failing"))
            ],
            [
                EventFile(output / "passing" / path, run_id, mapping)
                for run_id, path in enumerate(os.listdir(output / "passing"), start=2)
            ],
            config.factory,
        )
        analyzer.analyze()
        suggestions = analyzer.get_sorted_suggestions(src, type_=AnalysisType.LINE)
        self.assertEqual(3, len(suggestions))
        self.assertAlmostEquals(0.85416, suggestions[0].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.5, suggestions[1].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.375, suggestions[2].suspiciousness, delta=0.00001)
        self.assertEqual(1, len(suggestions[0].lines))
        self.assertIn(Location("main.py", 10), suggestions[0].lines)
        self.assertEqual(1, len(suggestions[1].lines))
        self.assertIn(Location("main.py", 6), suggestions[1].lines)
        self.assertEqual(1, len(suggestions[2].lines))
        self.assertIn(Location("main.py", 2), suggestions[2].lines)

    def test_time_assert_def_uses(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_WEIGHTS_DEF_USES)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line,test_def,test_use,test_assert",
            working=BaseTest.TEST_DIR,
            tests=r"test\.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        analyzer = TimeAnalyzer(
            TestAssertDefUsesModel,
            [
                EventFile(
                    output / "failing" / path,
                    run_id,
                    mapping,
                    True,
                )
                for run_id, path in enumerate(os.listdir(output / "failing"))
            ],
            [
                EventFile(output / "passing" / path, run_id, mapping)
                for run_id, path in enumerate(os.listdir(output / "passing"), start=2)
            ],
            config.factory,
        )
        analyzer.analyze()
        suggestions = analyzer.get_sorted_suggestions(src, type_=AnalysisType.LINE)
        self.assertEqual(3, len(suggestions))
        self.assertAlmostEquals(0.80555, suggestions[0].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.47222, suggestions[1].suspiciousness, delta=0.00001)
        self.assertAlmostEquals(0.33333, suggestions[2].suspiciousness, delta=0.00001)
        self.assertEqual(1, len(suggestions[0].lines))
        self.assertIn(Location("main.py", 10), suggestions[0].lines)
        self.assertEqual(1, len(suggestions[1].lines))
        self.assertIn(Location("main.py", 6), suggestions[1].lines)
        self.assertEqual(1, len(suggestions[2].lines))
        self.assertIn(Location("main.py", 2), suggestions[2].lines)

    def test_distances(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_WEIGHTS_DISTANCES)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line,test_def,test_use,test_assert",
            working=BaseTest.TEST_DIR,
            tests=r"test\.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        expectations = [
            [0, 1, 2, 3, 4, 5, 6, 7],
            [0, 1, 2, 2, 4, 1, 6, 7],
            [0, 1, 2, 3, 1, 2, 6, 7],
            [0, 2, 3, 4, 4, 1, 6, 7],
            [0, 2, 4, 4, 1, 2, 6, 7],
        ]
        lines = [WeightedAnalyses("test.py", i) for i in [12, 11, 10, 9, 8, 7, 2, 1]]
        for model_class, expected in zip(
            [
                TestLineModel,
                TestDefUseModel,
                TestDefUsesModel,
                TestAssertDefUseModel,
                TestAssertDefUsesModel,
            ],
            expectations,
        ):
            analyzer = TimeAnalyzer(
                model_class,
                [
                    EventFile(
                        output / "failing" / path,
                        run_id,
                        mapping,
                        True,
                    )
                    for run_id, path in enumerate(os.listdir(output / "failing"))
                ],
                [
                    EventFile(output / "passing" / path, run_id, mapping)
                    for run_id, path in enumerate(
                        os.listdir(output / "passing"), start=2
                    )
                ],
                config.factory,
            )
            analyzer.analyze()
            model = analyzer.model
            distances = model.get_distances()
            for line, distance in zip(lines, distances):
                self.assertEqual(
                    expected.pop(0), distances[distance], f"Failed for {line}"
                )
