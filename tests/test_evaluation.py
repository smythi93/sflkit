import random
from typing import Optional

from sflkit.analysis.suggestion import Suggestion, Location
from sflkit.evaluation import Average, Rank, Scenario
from utils import BaseTest


class TestEvaluation(BaseTest):
    def setUp(self):
        random.seed(0)
        self.suggestions = [
            Suggestion([Location("a.py", 1)], 0.5),
            Suggestion([Location("a.py", 2)], 0.3),
            Suggestion([Location("a.py", 3)], 0.7),
            Suggestion([Location("a.py", 4)], 0.1),
            Suggestion([Location("a.py", 5)], 0.9),
            Suggestion([Location("a.py", 6)], 0.2),
            Suggestion([Location("a.py", 7)], 0.8),
            Suggestion([Location("a.py", 8)], 0.4),
            Suggestion([Location("a.py", 9)], 0.6),
            Suggestion([Location("a.py", 10)], 0.0),
        ]

    def get_rank(self, multi: bool = False):
        suggestions = (
            self.suggestions
            if not multi
            else self.suggestions
            + [
                Suggestion(
                    [Location("a.py", 11), Location("a.py", 12), Location("a.py", 13)],
                    0.55,
                )
            ]
        )
        return (
            Rank(suggestions),
            {
                Location("a.py", 2),
                Location("a.py", 6),
                Location("a.py", 7),
                Location("a.py", 8),
            },
        )

    def get_top_n(
        self, n: int, scenario: Optional[Scenario] = None, multi: bool = False
    ):
        rank, locations = self.get_rank(multi=multi)
        return rank.top_n(
            locations,
            n,
            scenario=scenario,
            repeat=10000,
        )

    def get_exam(self, scenario: Optional[Scenario] = None):
        rank, locations = self.get_rank(multi=True)
        return rank.exam(
            locations,
            scenario=scenario,
        )

    def get_wasted_effort(self, scenario: Optional[Scenario] = None):
        rank, locations = self.get_rank(multi=True)
        return rank.wasted_effort(
            locations,
            scenario=scenario,
        )

    def test_top_1(self):
        top_1 = self.get_top_n(1)
        self.assertAlmostEqual(0, top_1, delta=self.DELTA)

    def test_top_5(self):
        top_5 = self.get_top_n(5)
        self.assertAlmostEqual(0.2, top_5, delta=self.DELTA)

    def test_top_10(self):
        top_10 = self.get_top_n(10)
        self.assertAlmostEqual(0.4, top_10, delta=self.DELTA)

    def test_top_5_multi(self):
        top_5_multi = self.get_top_n(5, multi=True)
        self.assertAlmostEqual(0.14285, top_5_multi, delta=0.05)

    def test_top_1_avg(self):
        top_1_avg = self.get_top_n(1, scenario=Scenario.AVG_CASE)
        self.assertAlmostEqual(0, top_1_avg, delta=self.DELTA)

    def test_top_5_avg(self):
        top_5_avg = self.get_top_n(5, scenario=Scenario.AVG_CASE)
        self.assertAlmostEqual(0.5, top_5_avg, delta=self.DELTA)

    def test_top_10_avg(self):
        top_10_avg = self.get_top_n(10, scenario=Scenario.AVG_CASE)
        self.assertAlmostEqual(1, top_10_avg, delta=self.DELTA)

    def test_top_5_avg_multi(self):
        top_5_avg_multi = self.get_top_n(5, scenario=Scenario.AVG_CASE, multi=True)
        self.assertAlmostEqual(0.35714, top_5_avg_multi, delta=0.005)

    def test_top_1_best(self):
        top_1_best = self.get_top_n(1, scenario=Scenario.BEST_CASE)
        self.assertAlmostEqual(0, top_1_best, delta=self.DELTA)

    def test_top_5_best(self):
        top_5_best = self.get_top_n(5, scenario=Scenario.BEST_CASE)
        self.assertAlmostEqual(1, top_5_best, delta=self.DELTA)

    def test_top_10_best(self):
        top_10_best = self.get_top_n(10, scenario=Scenario.BEST_CASE)
        self.assertAlmostEqual(1, top_10_best, delta=self.DELTA)

    def test_top_5_best_multi(self):
        top_5_best_multi = self.get_top_n(5, scenario=Scenario.BEST_CASE, multi=True)
        self.assertAlmostEqual(0.71429, top_5_best_multi, delta=0.005)

    def test_top_1_worst(self):
        top_1_worst = self.get_top_n(1, scenario=Scenario.WORST_CASE)
        self.assertAlmostEqual(0, top_1_worst, delta=self.DELTA)

    def test_top_5_worst(self):
        top_5_worst = self.get_top_n(5, scenario=Scenario.WORST_CASE)
        self.assertAlmostEqual(0.25, top_5_worst, delta=self.DELTA)

    def test_top_10_worst(self):
        top_10_worst = self.get_top_n(10, scenario=Scenario.WORST_CASE)
        self.assertAlmostEqual(1, top_10_worst, delta=self.DELTA)

    def test_top_5_worst_multi(self):
        top_5_worst_multi = self.get_top_n(5, scenario=Scenario.WORST_CASE, multi=True)
        self.assertAlmostEqual(0.17857, top_5_worst_multi, delta=0.005)

    def test_exam_avg(self):
        exam_avg = self.get_exam(scenario=Scenario.AVG_CASE)
        self.assertAlmostEqual(9 / 13, exam_avg, delta=self.DELTA)

    def test_exam_best(self):
        exam_best = self.get_exam(scenario=Scenario.BEST_CASE)
        self.assertAlmostEqual(2 / 13, exam_best, delta=self.DELTA)

    def test_exam_worst(self):
        exam_worst = self.get_exam(scenario=Scenario.WORST_CASE)
        self.assertAlmostEqual(11 / 13, exam_worst, delta=self.DELTA)

    def test_exam(self):
        exam = self.get_exam()
        self.assertAlmostEqual((2 + 9 + 10 + 11) / (13 * 4), exam, delta=self.DELTA)

    def test_wasted_effort_avg(self):
        wasted_effort_avg = self.get_wasted_effort(scenario=Scenario.AVG_CASE)
        self.assertAlmostEqual(9, wasted_effort_avg, delta=self.DELTA)

    def test_wasted_effort_best(self):
        wasted_effort_best = self.get_wasted_effort(scenario=Scenario.BEST_CASE)
        self.assertAlmostEqual(2, wasted_effort_best, delta=self.DELTA)

    def test_wasted_effort_worst(self):
        wasted_effort_worst = self.get_wasted_effort(scenario=Scenario.WORST_CASE)
        self.assertAlmostEqual(11, wasted_effort_worst, delta=self.DELTA)

    def test_wasted_effort(self):
        wasted_effort = self.get_wasted_effort()
        self.assertAlmostEqual((2 + 9 + 10 + 11) / 4, wasted_effort, delta=self.DELTA)


class TestRankInternals(BaseTest):
    """Locks in the parts of Rank that the fast paths rely on."""

    def setUp(self):
        random.seed(0)
        self.suggestions = [
            Suggestion([Location("a.py", 1), Location("a.py", 2)], 0.5),
            Suggestion([Location("a.py", 2), Location("a.py", 3)], 0.9),
            Suggestion([Location("a.py", 4)], 0.5),
            Suggestion([], 0.7),
            Suggestion([Location("b.py", 1)], 0.1),
        ]

    def test_repeated_top_n_does_not_drift(self):
        # n=1 leaves two candidates, so this goes through the sampling branch;
        # from the same seed the answer must not move between calls.
        rank = Rank(self.suggestions)
        faulty = {Location("a.py", 2)}
        results = []
        for _ in range(3):
            random.seed(0)
            results.append(rank.top_n(faulty, 1, repeat=1000))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertAlmostEqual(0.5, results[0], delta=0.05)

    def test_pool_keeps_first_seen_order_and_drops_duplicates(self):
        rank = Rank(self.suggestions)
        # a.py:2 is in the most suspicious suggestion and in a later one; it may
        # only be counted once, at the position it was first seen.
        self.assertEqual(
            [Location("a.py", 2), Location("a.py", 3), Location("a.py", 1)],
            rank._pool(3),
        )
        self.assertEqual(rank._pool(3), rank._pool(3))

    def test_metric_is_applied_for_every_line_of_every_suggestion(self):
        # The metric may be stateful (see Average), so the number and the order
        # of the calls is part of the behaviour.
        calls = []

        def metric(suspiciousness, current):
            calls.append((suspiciousness, current))
            return max(suspiciousness, current)

        Rank(self.suggestions, metric=metric)
        # once per (suggestion, line) while folding, once per location while ranking
        self.assertEqual(6 + 5, len(calls))
        self.assertEqual((0.9, float("-inf")), calls[0])

    def test_average_metric_reaches_every_location(self):
        average = Average()
        Rank(self.suggestions, metric=average.average)
        self.assertEqual(6 + 5, average.number_of_locations)

    def test_scenarios_agree_with_the_unsampled_scores(self):
        rank = Rank(self.suggestions, total_number_of_locations=10)
        faulty = {Location("a.py", 3), Location("b.py", 1)}
        # a.py:3 shares rank 1 with a.py:2, b.py:1 is alone at rank 5
        self.assertEqual(1.0, rank.get_rank(faulty, Scenario.BEST_CASE))
        self.assertEqual(5, rank.get_rank(faulty, Scenario.WORST_CASE))
        self.assertEqual(1.0, rank.get_rank(faulty, Scenario.AVG_CASE))
        self.assertAlmostEqual(3.0, rank.get_rank(faulty), delta=self.DELTA)
        self.assertEqual(2, rank.wasted_effort(faulty, Scenario.BEST_CASE))
        self.assertEqual(5, rank.wasted_effort(faulty, Scenario.WORST_CASE))
        self.assertAlmostEqual(3.5, rank.wasted_effort(faulty), delta=self.DELTA)


class TestSuggestionOrdering(BaseTest):
    def test_suggestions_compare_by_suspiciousness(self):
        low = Suggestion([Location("a.py", 1)], 0.25)
        high = Suggestion([Location("a.py", 2)], 0.75)
        self.assertLess(low, high)
        self.assertGreater(high, low)
        self.assertLessEqual(low, high)
        self.assertGreaterEqual(high, low)
        self.assertEqual([high, low], sorted([low, high], reverse=True))

    def test_suggestions_still_compare_against_plain_numbers(self):
        suggestion = Suggestion([Location("a.py", 1)], 0.5)
        self.assertTrue(suggestion < 0.75)
        self.assertTrue(suggestion > 0.25)
        self.assertTrue(suggestion <= 0.5)
        self.assertTrue(suggestion >= 0.5)

    def test_locations_hash_consistently_with_equality(self):
        a = Location("a.py", 1)
        b = Location("a.py", 1)
        c = Location("a.py", 2)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertEqual(hash(("a.py", 1)), hash(a))
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, "a.py:1")
        self.assertEqual(1, len({a, b}))

    def test_locations_survive_a_round_trip(self):
        import copy
        import pickle

        location = Location("a.py", 7)
        for clone in (copy.deepcopy(location), pickle.loads(pickle.dumps(location))):
            self.assertEqual(location, clone)
            self.assertEqual(hash(location), hash(clone))
