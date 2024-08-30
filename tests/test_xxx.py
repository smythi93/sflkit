import os
from pathlib import Path

from sflkit import Config, instrument_config
from sflkit.analysis.analysis_type import AnalysisType
from sflkit.analysis.suggestion import Location
from sflkit.mapping import EventMapping
from sflkit.model import EventFile
from sflkit.runners import PytestRunner
from sflkit.xxx.analyzer import SliceAnalyzer
from sflkit.xxx.models import TestLineModel, TestDefUseModel, TestFunctionModel
from utils import BaseTest


class TestXXX(BaseTest):
    def test_xxx_function(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_XXX_SETUP)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line,test_start,test_end",
            working=BaseTest.TEST_DIR,
            tests=r"test\.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        analyzer = SliceAnalyzer(
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

    def test_xxx_line(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_XXX_LINES)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line",
            working=BaseTest.TEST_DIR,
            tests=r"test\.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        analyzer = SliceAnalyzer(
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

    def test_xxx_def_use(self):
        src = Path(BaseTest.TEST_RESOURCES, self.TEST_XXX_DEF_USE)
        config = Config.create(
            path=str(src),
            language="python",
            events="line",
            predicates="line",
            test_events="test_line,test_def,test_use",
            working=BaseTest.TEST_DIR,
            tests=r"test\.py",
            mapping_path=self.TEST_MAPPING,
        )
        instrument_config(config)
        runner = PytestRunner(set_python_path=True)
        output = Path(BaseTest.TEST_DIR, "events").absolute()
        runner.run(Path(BaseTest.TEST_DIR), output, files=["test.py"])
        mapping = EventMapping.load(config)
        analyzer = SliceAnalyzer(
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
