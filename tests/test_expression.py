import os

from sflkit import Analyzer
from sflkit.analysis.analysis_type import AnalysisType
from sflkit.analysis.spectra import DefUse
from utils import BaseTest


class ExpressionTest(BaseTest):
    EXPRESSIONS = "expressions"

    def test_expression(self):
        config, relevant_event_files, irrelevant_event_files = (
            self.run_analysis_event_files(
                self.EXPRESSIONS,
                events="",
                predicates="def_use",
                relevant=[["2 - 3"], ["2 * (1 - 1)"]],
                irrelevant=[
                    ["2 + 3"],
                    ["5 / 6"],
                    ["1 + (2 * 3)"],
                    ["(1 + 2) * 3"],
                    ["1 + 1"],
                    ["1 - 0"],
                    ["~ 4"],
                ],
                access="evaluate.py",
            )
        )
        analyzer = Analyzer(
            relevant_event_files, irrelevant_event_files, config.factory, workers=1
        )
        analyzer.analyze()
        expected_def_use = {
            # evaluate.py
            ("arg", "evaluate.py", 7): {
                ("evaluate.py", 8),
            },
            ("term", "evaluate.py", 8): {
                ("evaluate.py", 9),
            },
            ("result", "evaluate.py", 9): {
                ("evaluate.py", 10),
            },
            # expr/parse.py
            # parse()
            ("s", os.path.join("expr", "parse.py"), 15): {
                (os.path.join("expr", "parse.py"), 16),
            },
            ("s", os.path.join("expr", "parse.py"), 16): {
                (os.path.join("expr", "parse.py"), 17),
            },
            ("s", os.path.join("expr", "parse.py"), 17): {
                (os.path.join("expr", "parse.py"), 18),
                (os.path.join("expr", "parse.py"), 19),
                (os.path.join("expr", "parse.py"), 20),
            },
            ("s", os.path.join("expr", "parse.py"), 19): {
                (os.path.join("expr", "parse.py"), 18),
            },
            ("s", os.path.join("expr", "parse.py"), 19): {
                (os.path.join("expr", "parse.py"), 20),
            },
            ("s", os.path.join("expr", "parse.py"), 20): {
                (os.path.join("expr", "parse.py"), 21),
            },
            ("tokens", os.path.join("expr", "parse.py"), 21): {
                (os.path.join("expr", "parse.py"), 22),
                (os.path.join("expr", "parse.py"), 23),
                (os.path.join("expr", "parse.py"), 24),
            },
            ("term", os.path.join("expr", "parse.py"), 23): {
                (os.path.join("expr", "parse.py"), 25),
            },
            # parse_terminal()
            ("tokens", os.path.join("expr", "parse.py"), 28): {
                (os.path.join("expr", "parse.py"), 29),
                (os.path.join("expr", "parse.py"), 33),
                (os.path.join("expr", "parse.py"), 34),
            },
            ("token", os.path.join("expr", "parse.py"), 29): {
                (os.path.join("expr", "parse.py"), 30),
                (os.path.join("expr", "parse.py"), 31),
                (os.path.join("expr", "parse.py"), 32),
            },
            ("term", os.path.join("expr", "parse.py"), 33): {
                (os.path.join("expr", "parse.py"), 36),
            },
            ("token", os.path.join("expr", "parse.py"), 34): {
                (os.path.join("expr", "parse.py"), 35),
            },
            # parse_neg()
            ("tokens", os.path.join("expr", "parse.py"), 41): {
                (os.path.join("expr", "parse.py"), 42),
                (os.path.join("expr", "parse.py"), 43),
                (os.path.join("expr", "parse.py"), 44),
            },
            ("term", os.path.join("expr", "parse.py"), 42): {
                (os.path.join("expr", "parse.py"), 45),
                (os.path.join("expr", "parse.py"), 47),
            },
            # parse_mul_div()
            ("tokens", os.path.join("expr", "parse.py"), 50): {
                (os.path.join("expr", "parse.py"), 51),
                (os.path.join("expr", "parse.py"), 52),
                (os.path.join("expr", "parse.py"), 53),
                (os.path.join("expr", "parse.py"), 55),
                (os.path.join("expr", "parse.py"), 57),
            },
            ("term", os.path.join("expr", "parse.py"), 51): {
                (os.path.join("expr", "parse.py"), 55),
                (os.path.join("expr", "parse.py"), 57),
                (os.path.join("expr", "parse.py"), 59),
            },
            ("token", os.path.join("expr", "parse.py"), 53): {
                (os.path.join("expr", "parse.py"), 54),
            },
            # parse_add_sub()
            ("tokens", os.path.join("expr", "parse.py"), 62): {
                (os.path.join("expr", "parse.py"), 63),
                (os.path.join("expr", "parse.py"), 64),
                (os.path.join("expr", "parse.py"), 65),
                (os.path.join("expr", "parse.py"), 67),
                (os.path.join("expr", "parse.py"), 69),
            },
            ("term", os.path.join("expr", "parse.py"), 63): {
                (os.path.join("expr", "parse.py"), 67),
                (os.path.join("expr", "parse.py"), 69),
                (os.path.join("expr", "parse.py"), 71),
            },
            ("token", os.path.join("expr", "parse.py"), 65): {
                (os.path.join("expr", "parse.py"), 66),
            },
            # expr/arithmetic.py
            # Binary.__init__()
            ("left", os.path.join("expr", "arithmetic.py"), 7): {
                (os.path.join("expr", "arithmetic.py"), 8),
            },
            ("right", os.path.join("expr", "arithmetic.py"), 7): {
                (os.path.join("expr", "arithmetic.py"), 9),
            },
            ("self.left", os.path.join("expr", "arithmetic.py"), 8): {
                (os.path.join("expr", "arithmetic.py"), 14),
                (os.path.join("expr", "arithmetic.py"), 19),
                (os.path.join("expr", "arithmetic.py"), 24),
                (os.path.join("expr", "arithmetic.py"), 29),
            },
            ("self.right", os.path.join("expr", "arithmetic.py"), 9): {
                (os.path.join("expr", "arithmetic.py"), 14),
                (os.path.join("expr", "arithmetic.py"), 19),
                (os.path.join("expr", "arithmetic.py"), 24),
                (os.path.join("expr", "arithmetic.py"), 29),
            },
            # Neg.__init__()
            ("term", os.path.join("expr", "arithmetic.py"), 33): {
                (os.path.join("expr", "arithmetic.py"), 34),
            },
            ("self.term", os.path.join("expr", "arithmetic.py"), 34): {
                (os.path.join("expr", "arithmetic.py"), 37),
            },
            # Constant.__init__()
            ("value", os.path.join("expr", "arithmetic.py"), 41): {
                (os.path.join("expr", "arithmetic.py"), 42),
            },
            ("self.value", os.path.join("expr", "arithmetic.py"), 42): {
                (os.path.join("expr", "arithmetic.py"), 45),
            },
        }

        actual = {}

        for analysis in analyzer.get_analysis_by_type(AnalysisType.DEF_USE):
            if not isinstance(analysis, DefUse):
                continue
            key = (analysis.var, analysis.file, analysis.line)
            if key not in actual:
                actual[key] = set()
            actual[key].add((analysis.use_file, analysis.use_line))

        self.assertEqual(expected_def_use, actual)
