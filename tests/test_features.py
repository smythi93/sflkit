import unittest
from concurrent.futures.thread import ThreadPoolExecutor

from sflkit.analysis.analysis_type import MetaEvent
from sflkit.analysis.factory import DefUseFactory
from sflkit.analysis.predicate import Branch
from sflkit.analysis.spectra import Line
from sflkit.events.event_file import EventFile
from sflkit.events.mapping import EventMapping
from sflkit.features.handler import EventHandler, FeatureBuilder
from sflkit.features.value import FeatureValue, BinaryFeature, TertiaryFeature
from sflkit.features.vector import FeatureVector
from sflkit.model.model import Model
from sflkit.model.scope import Scope
from sflkitlib.events.event import DefEvent, UseEvent
from sflkit.runners.run import TestResult
from utils import BaseTest


class ValueTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.true_val = FeatureValue.TRUE
        cls.false_val = FeatureValue.FALSE
        cls.undefined_val = FeatureValue.UNDEFINED

    def test_true(self):
        self.assertEqual(self.true_val.value, 1)
        self.assertEqual(repr(self.true_val), "TRUE")

    def test_false(self):
        self.assertEqual(self.false_val.value, 0)
        self.assertEqual(repr(self.false_val), "FALSE")

    def test_undefined(self):
        self.assertEqual(self.undefined_val.value, -1)
        self.assertEqual(repr(self.undefined_val), "UNDEFINED")

    def test_or_operation(self):
        self.assertEqual(self.true_val | self.true_val, self.true_val)
        self.assertEqual(self.true_val | self.false_val, self.true_val)
        self.assertEqual(self.true_val | self.undefined_val, self.true_val)
        self.assertEqual(self.false_val | self.false_val, self.false_val)
        self.assertEqual(self.false_val | self.true_val, self.true_val)
        self.assertEqual(self.false_val | self.undefined_val, self.false_val)
        self.assertEqual(self.undefined_val | self.true_val, self.true_val)
        self.assertEqual(self.undefined_val | self.false_val, self.false_val)
        self.assertEqual(self.undefined_val | self.undefined_val, self.undefined_val)

    def test_or_with_bool(self):
        self.assertEqual(self.true_val | True, self.true_val)
        self.assertEqual(self.true_val | False, self.true_val)
        self.assertEqual(self.false_val | True, self.true_val)
        self.assertEqual(self.false_val | False, self.false_val)
        self.assertEqual(self.undefined_val | True, self.true_val)
        self.assertEqual(self.undefined_val | False, self.false_val)
        self.assertEqual(self.undefined_val | None, self.undefined_val)

    def test_not_operation(self):
        self.assertEqual(~self.true_val, self.false_val)
        self.assertEqual(~self.false_val, self.true_val)
        self.assertEqual(~self.undefined_val, self.undefined_val)


class FeatureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.line = Line(MetaEvent("test.py", 1))
        cls.branch = Branch(MetaEvent("test.py", 2, then_id=1, else_id=2))
        cls.bin_feature = BinaryFeature(str(cls.line), cls.line)
        cls.ter_feature = TertiaryFeature(str(cls.branch), cls.branch)

    def test_binary_feature_default(self):
        self.assertEqual(self.bin_feature.default(), FeatureValue.FALSE)

    def test_tertiary_feature_default(self):
        self.assertEqual(self.ter_feature.default(), FeatureValue.UNDEFINED)

    def test_lt(self):
        self.assertLess(self.ter_feature, self.bin_feature)

    def test_gt(self):
        self.assertGreater(self.bin_feature, self.ter_feature)

    def test_eq(self):
        self.assertEqual(self.bin_feature, self.bin_feature)
        self.assertNotEqual(self.bin_feature, self.ter_feature)
        self.assertEqual(self.ter_feature, self.ter_feature)


class VectorTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.vector_pass = FeatureVector(
            EventFile("EVENTS", 1, EventMapping()), TestResult.PASSING
        )
        cls.vector_fail = FeatureVector(
            EventFile("EVENTS", 2, EventMapping()), TestResult.FAILING
        )
        cls.bin_feature_1 = BinaryFeature("line_1", Line(MetaEvent("test.py", 1)))
        cls.bin_feature_2 = BinaryFeature("line_2", Line(MetaEvent("test.py", 2)))
        cls.ter_feature_1 = TertiaryFeature(
            "branch_1", Branch(MetaEvent("test.py", 2, then_id=1, else_id=2))
        )
        cls.ter_feature_2 = TertiaryFeature(
            "branch_2",
            Branch(MetaEvent("test.py", 2, then_id=1, else_id=2), then=False),
        )
        cls.vector_pass.set_feature(cls.bin_feature_1, FeatureValue.TRUE)
        cls.vector_pass.set_feature(cls.bin_feature_2, FeatureValue.FALSE)
        cls.vector_pass.set_feature(cls.ter_feature_1, FeatureValue.FALSE)
        cls.vector_pass.set_feature(cls.ter_feature_2, FeatureValue.TRUE)
        cls.vector_fail.set_feature(cls.bin_feature_1, FeatureValue.FALSE)
        cls.vector_fail.set_feature(cls.bin_feature_2, FeatureValue.FALSE)
        cls.vector_fail.set_feature(cls.ter_feature_1, FeatureValue.UNDEFINED)
        cls.features = [
            cls.bin_feature_1,
            cls.bin_feature_2,
            cls.ter_feature_1,
            cls.ter_feature_2,
        ]

    def test_feature_set(self):
        self.assertEqual(
            {
                self.bin_feature_1,
                self.bin_feature_2,
                self.ter_feature_1,
                self.ter_feature_2,
            },
            self.vector_pass.get_features_set(),
        )
        self.assertEqual(
            {self.bin_feature_1, self.bin_feature_2, self.ter_feature_1},
            self.vector_fail.get_features_set(),
        )

    def test_get_feature_value(self):
        self.assertEqual(
            FeatureValue.TRUE,
            self.vector_pass.get_feature_value(self.bin_feature_1),
        )
        self.assertEqual(
            FeatureValue.FALSE,
            self.vector_pass.get_feature_value(self.bin_feature_2),
        )
        self.assertEqual(
            FeatureValue.FALSE,
            self.vector_pass.get_feature_value(self.ter_feature_1),
        )
        self.assertEqual(
            FeatureValue.TRUE,
            self.vector_pass.get_feature_value(self.ter_feature_2),
        )
        self.assertEqual(
            FeatureValue.FALSE,
            self.vector_fail.get_feature_value(self.bin_feature_1),
        )
        self.assertEqual(
            FeatureValue.FALSE,
            self.vector_fail.get_feature_value(self.bin_feature_2),
        )
        self.assertEqual(
            FeatureValue.UNDEFINED,
            self.vector_fail.get_feature_value(self.ter_feature_1),
        )

    def test_feature_dict(self):
        self.assertEqual(
            {
                self.bin_feature_1: FeatureValue.TRUE,
                self.bin_feature_2: FeatureValue.FALSE,
                self.ter_feature_1: FeatureValue.FALSE,
                self.ter_feature_2: FeatureValue.TRUE,
            },
            self.vector_pass.get_features(),
        )
        self.assertEqual(
            {
                self.bin_feature_1: FeatureValue.FALSE,
                self.bin_feature_2: FeatureValue.FALSE,
                self.ter_feature_1: FeatureValue.UNDEFINED,
            },
            self.vector_fail.get_features(),
        )

    def test_to_vector(self):
        self.assertEqual(
            [
                FeatureValue.TRUE,
                FeatureValue.FALSE,
                FeatureValue.FALSE,
                FeatureValue.TRUE,
            ],
            self.vector_pass.vector(self.features),
        )
        self.assertEqual(
            [
                FeatureValue.FALSE,
                FeatureValue.FALSE,
                FeatureValue.UNDEFINED,
                FeatureValue.UNDEFINED,
            ],
            self.vector_fail.vector(self.features),
        )

    def test_to_num_vector(self):
        self.assertEqual(
            [1, 0, 0, 1],
            self.vector_pass.num_vector(self.features),
        )
        self.assertEqual(
            [0, 0, -1, -1],
            self.vector_fail.num_vector(self.features),
        )

    def test_to_dict_vector(self):
        self.assertEqual(
            {
                self.bin_feature_1: FeatureValue.TRUE,
                self.bin_feature_2: FeatureValue.FALSE,
                self.ter_feature_1: FeatureValue.FALSE,
                self.ter_feature_2: FeatureValue.TRUE,
            },
            self.vector_pass.dict_vector(self.features),
        )
        self.assertEqual(
            {
                self.bin_feature_1: FeatureValue.FALSE,
                self.bin_feature_2: FeatureValue.FALSE,
                self.ter_feature_1: FeatureValue.UNDEFINED,
                self.ter_feature_2: FeatureValue.UNDEFINED,
            },
            self.vector_fail.dict_vector(self.features),
        )

    def test_to_num_dict_vector(self):
        self.assertEqual(
            {
                "line_1": 1,
                "line_2": 0,
                "branch_1": 0,
                "branch_2": 1,
            },
            self.vector_pass.num_dict_vector(self.features),
        )
        self.assertEqual(
            {
                "line_1": 0,
                "line_2": 0,
                "branch_1": -1,
                "branch_2": -1,
            },
            self.vector_fail.num_dict_vector(self.features),
        )

    def test_to_tuple(self):
        self.assertEqual(
            (
                (self.bin_feature_1, FeatureValue.TRUE),
                (self.bin_feature_2, FeatureValue.FALSE),
                (self.ter_feature_1, FeatureValue.FALSE),
                (self.ter_feature_2, FeatureValue.TRUE),
            ),
            self.vector_pass.tuple(self.features),
        )
        self.assertEqual(
            (
                (self.bin_feature_1, FeatureValue.FALSE),
                (self.bin_feature_2, FeatureValue.FALSE),
                (self.ter_feature_1, FeatureValue.UNDEFINED),
                (self.ter_feature_2, FeatureValue.UNDEFINED),
            ),
            self.vector_fail.tuple(self.features),
        )

    def test_equality(self):
        self.assertEqual(self.vector_pass, self.vector_pass)
        self.assertEqual(self.vector_fail, self.vector_fail)
        self.assertNotEqual(self.vector_pass, self.vector_fail)
        self.assertNotEqual(self.vector_fail, self.vector_pass)

    def test_difference(self):
        self.assertEqual(
            3,
            self.vector_pass.difference(self.vector_fail, self.features),
        )
        self.assertEqual(
            3,
            self.vector_fail.difference(self.vector_pass, self.features),
        )


class ThreadVectorTest(unittest.TestCase):

    def test_thread_vector(self):

        features_values = []
        features = {}

        for n in range(10):
            features[n] = BinaryFeature(str(n), Line(MetaEvent("test.py", n)))
            features[n + 10] = TertiaryFeature(
                str(n + 10),
                Branch(MetaEvent("test.py", n + 10, then_id=1, else_id=2)),
            )

        for n in range(100):
            bin_feature = features[n % 10]
            ter_feature = features[(n % 10) + 10]
            bin_value = FeatureValue.TRUE if n % 2 == 0 else FeatureValue.FALSE
            ter_value = (
                FeatureValue.UNDEFINED
                if n % 2 == 0
                else (FeatureValue.TRUE if n % 3 == 0 else FeatureValue.FALSE)
            )
            if n % 20 - 10 >= 0:
                bin_value = ~bin_value
                ter_value = ~ter_value
            features_values.append((bin_feature, bin_value))
            features_values.append((ter_feature, ter_value))

        vector = FeatureVector(
            EventFile("EVENTS", 0, EventMapping()), TestResult.FAILING
        )

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for feature, value in features_values:
                futures.append(executor.submit(vector.set_feature, feature, value))
            for future in futures:
                future.result()

        for i in range(10):
            if i % 2 == 0:
                self.assertEqual(
                    FeatureValue.TRUE, vector.get_feature_value(features[i])
                )
            else:
                self.assertEqual(
                    FeatureValue.FALSE, vector.get_feature_value(features[i])
                )
            if i % 2 == 0:
                self.assertEqual(
                    FeatureValue.UNDEFINED, vector.get_feature_value(features[i + 10])
                )
            else:
                if i % 3 == 0:
                    self.assertEqual(
                        FeatureValue.TRUE, vector.get_feature_value(features[i + 10])
                    )
                else:
                    self.assertEqual(
                        FeatureValue.FALSE, vector.get_feature_value(features[i + 10])
                    )


class HandlerTest(BaseTest):
    @classmethod
    def setUpClass(cls):
        _, cls.failing, cls.passing = cls.run_analysis_event_files(
            cls.TEST_SUGGESTIONS,
            "line",
            "line",
            relevant=[["2", "1", "3"]],
            irrelevant=[["3", "2", "1"]],
        )
        cls.events = {
            1: Line(MetaEvent("main.py", 1)),
            5: Line(MetaEvent("main.py", 5)),
            6: Line(MetaEvent("main.py", 6)),
            7: Line(MetaEvent("main.py", 7)),
            9: Line(MetaEvent("main.py", 9)),
            10: Line(MetaEvent("main.py", 10)),
            12: Line(MetaEvent("main.py", 12)),
            13: Line(MetaEvent("main.py", 13)),
            16: Line(MetaEvent("main.py", 16)),
            19: Line(MetaEvent("main.py", 19)),
            20: Line(MetaEvent("main.py", 20)),
        }
        cls.features = {
            n: BinaryFeature(str(cls.events[n]), cls.events[n]) for n in cls.events
        }
        cls.failing_vector = {
            cls.features[1]: FeatureValue.TRUE,
            cls.features[5]: FeatureValue.TRUE,
            cls.features[6]: FeatureValue.TRUE,
            cls.features[7]: FeatureValue.TRUE,
            cls.features[9]: FeatureValue.TRUE,
            cls.features[10]: FeatureValue.TRUE,
            cls.features[12]: FeatureValue.FALSE,
            cls.features[13]: FeatureValue.FALSE,
            cls.features[16]: FeatureValue.TRUE,
            cls.features[19]: FeatureValue.TRUE,
            cls.features[20]: FeatureValue.TRUE,
        }
        cls.passing_vector = {
            cls.features[1]: FeatureValue.TRUE,
            cls.features[5]: FeatureValue.TRUE,
            cls.features[6]: FeatureValue.TRUE,
            cls.features[7]: FeatureValue.FALSE,
            cls.features[9]: FeatureValue.FALSE,
            cls.features[10]: FeatureValue.FALSE,
            cls.features[12]: FeatureValue.TRUE,
            cls.features[13]: FeatureValue.TRUE,
            cls.features[16]: FeatureValue.TRUE,
            cls.features[19]: FeatureValue.TRUE,
            cls.features[20]: FeatureValue.TRUE,
        }

    def _test_handler(self, handler):
        handler.handle_files(self.failing + self.passing)
        vectors = handler.get_vectors()
        failing = [vector for vector in vectors if vector.result == TestResult.FAILING]
        passing = [vector for vector in vectors if vector.result == TestResult.PASSING]
        self.assertEqual(1, len(failing))
        self.assertEqual(1, len(passing))
        fail_vector = failing[0]
        pass_vector = passing[0]
        self.assertEqual(self.failing_vector, fail_vector.get_features())
        self.assertEqual(self.passing_vector, pass_vector.get_features())

    def test_sequential_handler(self):
        self._test_handler(EventHandler(workers=1))

    def test_threaded_handler(self):
        self._test_handler(EventHandler(thread_support=True, workers=4))

    def test_copy(self):
        handler = EventHandler(thread_support=True, workers=4)
        handler.handle_files(self.failing + self.passing)
        handler_copy = handler.copy()
        self.assertEqual(handler.thread_support, handler_copy.thread_support)
        original_vectors = handler.get_vectors()
        copy_vectors = handler_copy.get_vectors()
        self.assertEqual(len(original_vectors), len(copy_vectors))
        for ov, cv in zip(original_vectors, copy_vectors):
            self.assertEqual(ov.get_features(), cv.get_features())

    def test_to_df(self):
        handler = EventHandler()
        handler.handle_files(self.failing + self.passing)
        df = handler.to_df(label="test")
        self.assertEqual(2, len(df))
        self.assertIn("label", df.columns)
        self.assertIn("failing", df.columns)
        for feature in self.features.values():
            self.assertIn(feature.name, df.columns)
        fail_row = df[df["failing"] == 1].iloc[0]
        pass_row = df[df["failing"] == 0].iloc[0]
        for feature in self.features.values():
            self.assertEqual(self.failing_vector[feature].value, fail_row[feature.name])
            self.assertEqual(self.passing_vector[feature].value, pass_row[feature.name])


class ScopeReleaseTest(unittest.TestCase):
    """
    Per-scope analysis state must die with its scope.

    Scope ids are handed out per function call, so anything a factory keeps per
    scope grows with the number of calls a run makes. The def-use factory used
    to keep one dict, and every DefEvent in it, for every call ever made: a
    20,000-call run retained 180,000 events.
    """

    def setUp(self):
        self.factory = DefUseFactory()
        self.run = EventFile("EVENTS", 0, EventMapping())

    def _define(self, scope: Scope, index: int) -> None:
        event = DefEvent("main.py", 1, 0, "x", index, index, "int")
        self.factory.get_analysis(event, self.run, scope)

    def test_leaving_a_scope_releases_its_definitions(self):
        for index in range(100):
            scope = Scope()
            self._define(scope, index)
            self.factory.exit_scope(self.run, scope.id)
        self.assertEqual(
            0,
            len(self.factory.def_stack[self.run]),
            "definitions of ended scopes are still retained",
        )

    def test_state_accumulates_while_scopes_are_live(self):
        scopes = [Scope() for _ in range(10)]
        for index, scope in enumerate(scopes):
            self._define(scope, index)
        self.assertEqual(
            10,
            len(self.factory.def_stack[self.run]),
            "a live scope must keep its definitions",
        )

    def test_model_reports_scope_exits_to_the_factory(self):
        model = Model(self.factory)
        model.prepare(self.run)
        model.enter_scope(self.run)
        self._define(model.variables[self.run], 0)
        self.assertEqual(1, len(self.factory.def_stack[self.run]))
        model.exit_scope(self.run)
        self.assertEqual(
            0,
            len(self.factory.def_stack[self.run]),
            "the model must tell factories when a scope ends",
        )


class DefUseResolutionTest(unittest.TestCase):
    """
    A use must find its definition through the scope chain.

    Looking only in the innermost scope missed everything a caller defined,
    which is why a map of every definition ever made was kept as a fallback.
    That map is keyed by ``id(value)``, so it grew without bound and, because
    CPython recycles ids, could match a definition of an unrelated object.
    """

    def setUp(self):
        self.factory = DefUseFactory()
        self.run = EventFile("EVENTS", 0, EventMapping())

    def _define(self, scope: Scope, var: str, var_id: int) -> None:
        self.factory.get_analysis(
            DefEvent("main.py", 1, 0, var, var_id, var_id, "int"), self.run, scope
        )

    def _use(self, scope: Scope, var: str, var_id: int):
        return self.factory.get_analysis(
            UseEvent("main.py", 2, 1, var, var_id), self.run, scope
        )

    def test_use_finds_a_definition_from_an_enclosing_scope(self):
        outer = Scope()
        self._define(outer, "x", 7)
        inner = outer.enter()
        self.assertTrue(
            self._use(inner, "x", 7), "a use must see the enclosing scope's definition"
        )

    def test_use_does_not_find_a_definition_from_a_dead_scope(self):
        outer = Scope()
        sibling = outer.enter()
        self._define(sibling, "x", 7)
        self.factory.exit_scope(self.run, sibling.id)
        other = outer.enter()
        self.assertFalse(
            self._use(other, "x", 7),
            "a definition from a scope that ended must not resolve",
        )

    def test_cross_thread_fallback_is_bounded(self):
        scope = Scope()
        for index in range(DefUseFactory.CROSS_THREAD_LIMIT + 500):
            self._define(scope, "x", index)
        self.assertLessEqual(
            len(self.factory.id_to_def[self.run]),
            DefUseFactory.CROSS_THREAD_LIMIT,
            "the cross-thread map must stay bounded",
        )


class ProcessParallelBuilderTest(BaseTest):
    """
    Spreading runs over worker processes must not change what is built.

    Runs are independent, so each worker can build from its share and the
    parent merges. What must hold is that the merged result is
    indistinguishable from building everything in one process.
    """

    EVENTS = "line,branch,def,use,function_enter,function_exit"

    def _event_files(self):
        _, relevant, irrelevant = self.run_analysis_event_files(
            self.TEST_SUGGESTIONS,
            self.EVENTS,
            "line,branch,def_use,scalar_pair",
            relevant=[["3", "2", "1"]],
            irrelevant=[["1", "2", "3"], ["2", "1", "3"], ["3", "1", "2"]],
        )
        return relevant + irrelevant

    @staticmethod
    def _vectors(handler):
        return {
            str(vector.run_id): {
                feature.name: value.value
                for feature, value in vector.get_features().items()
            }
            for vector in handler.builder.get_vectors()
        }

    def test_vectors_match_a_single_process(self):
        event_files = self._event_files()
        serial = EventHandler(workers=1)
        serial.handle_files(event_files)
        parallel = EventHandler(workers=1, processes=2)
        parallel.handle_files(event_files)
        self.assertTrue(self._vectors(serial), "no vectors were built")
        self.assertEqual(self._vectors(serial), self._vectors(parallel))

    def test_feature_set_matches_a_single_process(self):
        event_files = self._event_files()
        serial = EventHandler(workers=1)
        serial.handle_files(event_files)
        parallel = EventHandler(workers=1, processes=3)
        parallel.handle_files(event_files)
        self.assertEqual(
            {feature.name for feature in serial.builder.all_features},
            {feature.name for feature in parallel.builder.all_features},
        )
