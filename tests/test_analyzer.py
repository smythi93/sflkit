from sflkitlib.events.event import (
    LineEvent,
    BranchEvent,
    FunctionEnterEvent,
    LoopBeginEvent,
    DefEvent,
    UseEvent,
    LenEvent,
    FunctionExitEvent,
)

from sflkit import Analyzer
from sflkit.analysis.predicate import (
    Branch,
    ScalarPair,
    VariablePredicate,
    NonePredicate,
    ReturnPredicate,
    EmptyStringPredicate,
    EmptyBytesPredicate,
    IsAsciiPredicate,
    ContainsDigitPredicate,
    ContainsSpecialPredicate,
    Condition,
    FunctionErrorPredicate,
    Comp,
)
from sflkit.analysis.spectra import Line, Function, Loop, DefUse, Length
from sflkit.model.model import MetaModel
from utils import BaseTest


class TestAnalyzer(BaseTest):
    def test_dumps_spectra(self):
        line = Line(LineEvent(self.ACCESS, 1, 0))
        function = Function(FunctionEnterEvent(self.ACCESS, 1, 0, "main", 0))
        loop = Loop(LoopBeginEvent(self.ACCESS, 1, 2, 0))
        def_use = DefUse(
            DefEvent(self.ACCESS, 1, 3, "var"), UseEvent(self.ACCESS, 1, 4, "var")
        )
        length = Length(LenEvent(self.ACCESS, 1, 5, "var", 0, 1))
        for spectrum in [line, function, loop, def_use, length]:
            spectrum.failed_observed = 1
            spectrum.failed_not_observed = 0
            spectrum.passed_observed = 1
            spectrum.passed_not_observed = 1
            spectrum.failed = 1
            spectrum.passed = 2
        analyzer = Analyzer(
            meta_model=MetaModel(
                {line, function, loop, def_use, length},
            )
        )
        dump = analyzer.dumps()
        reconstructed = Analyzer.loads(dump)
        analysis = reconstructed.get_analysis()
        self.assertIn(line, analysis)
        self.assertIn(function, analysis)
        self.assertIn(loop, analysis)
        self.assertIn(def_use, analysis)
        self.assertIn(length, analysis)
        for spectrum in analysis:
            self.assertEqual(1, spectrum.failed_observed)
            self.assertEqual(0, spectrum.failed_not_observed)
            self.assertEqual(1, spectrum.passed_observed)
            self.assertEqual(1, spectrum.passed_not_observed)
            self.assertEqual(1, spectrum.failed)
            self.assertEqual(2, spectrum.passed)

    def test_dumps_predicates(self):
        branch = Branch(BranchEvent(self.ACCESS, 1, 0, 0, 1), then=True)
        scalar_pair = ScalarPair(
            DefEvent(self.ACCESS, 1, 1, var="x"),
            Comp.EQ,
            "y",
        )
        variable = VariablePredicate(DefEvent(self.ACCESS, 1, 3, var="x"), Comp.EQ)
        none = NonePredicate(DefEvent(self.ACCESS, 1, 4, var="x"))
        return_ = ReturnPredicate(
            FunctionExitEvent(self.ACCESS, 1, 5, "f", 0, "f_tmp", 1), Comp.EQ
        )
        empty_string = EmptyStringPredicate(DefEvent(self.ACCESS, 1, 6, var="x"))
        empty_bytes = EmptyBytesPredicate(DefEvent(self.ACCESS, 1, 7, var="x"))
        ascii_ = IsAsciiPredicate(DefEvent(self.ACCESS, 1, 8, var="x"))
        digit = ContainsDigitPredicate(DefEvent(self.ACCESS, 1, 9, var="x"))
        special = ContainsSpecialPredicate(DefEvent(self.ACCESS, 1, 10, var="x"))
        condition = Condition(self.ACCESS, 1, "x < 3")
        function_error = FunctionErrorPredicate(self.ACCESS, 1, "f")

        for predicate in [
            branch,
            scalar_pair,
            variable,
            none,
            return_,
            empty_string,
            empty_bytes,
            ascii_,
            digit,
            special,
            condition,
            function_error,
        ]:
            predicate.failed_observed = 1
            predicate.failed_not_observed = 0
            predicate.passed_observed = 1
            predicate.passed_not_observed = 1
            predicate.failed = 1
            predicate.passed = 2
            predicate.context = 1
            predicate.fail_true = 2
            predicate.fail_false = 3
            predicate.increase_true = 4
            predicate.increase_false = 5

        analyzer = Analyzer(
            meta_model=MetaModel(
                {
                    branch,
                    scalar_pair,
                    variable,
                    none,
                    return_,
                    empty_string,
                    empty_bytes,
                    ascii_,
                    digit,
                    special,
                    condition,
                    function_error,
                }
            )
        )
        dump = analyzer.dumps()
        reconstructed = Analyzer.loads(dump)
        analysis = reconstructed.get_analysis()

        self.assertIn(branch, analysis)
        self.assertIn(scalar_pair, analysis)
        self.assertIn(variable, analysis)
        self.assertIn(none, analysis)
        self.assertIn(return_, analysis)
        self.assertIn(empty_string, analysis)
        self.assertIn(empty_bytes, analysis)
        self.assertIn(ascii_, analysis)
        self.assertIn(digit, analysis)
        self.assertIn(special, analysis)
        self.assertIn(condition, analysis)
        self.assertIn(function_error, analysis)

        for predicate in analysis:
            self.assertEqual(1, predicate.failed_observed)
            self.assertEqual(0, predicate.failed_not_observed)
            self.assertEqual(1, predicate.passed_observed)
            self.assertEqual(1, predicate.passed_not_observed)
            self.assertEqual(1, predicate.failed)
            self.assertEqual(2, predicate.passed)
            self.assertEqual(1, predicate.context)
            self.assertEqual(2, predicate.fail_true)
            self.assertEqual(3, predicate.fail_false)
            self.assertEqual(4, predicate.increase_true)
            self.assertEqual(5, predicate.increase_false)
