import enum
import random
from operator import attrgetter, itemgetter
from typing import List, Dict, Callable, Set, Optional

from sflkit.analysis.suggestion import Suggestion, Location

_suspiciousness_of = attrgetter("suspiciousness")
_key_of = itemgetter(0)


class Average:
    def __init__(self):
        self.number_of_locations = 0

    def average(self, suspiciousness: float, current_suspiciousness: float):
        current_suspiciousness *= self.number_of_locations
        self.number_of_locations += 1
        return (current_suspiciousness + suspiciousness) / self.number_of_locations


class Scenario(enum.Enum):
    BEST_CASE = "best_case"
    AVG_CASE = "avg_case"
    WORST_CASE = "worst_case"


class Rank:
    def __init__(
        self,
        suggestions: List[Suggestion],
        metric: Callable[[float, float], float] = max,
        default_suspiciousness: float = float("-inf"),
        total_number_of_locations: Optional[int] = None,
    ):
        # Sorting on the suspiciousness directly instead of on the suggestions
        # yields the same order, because that is the only thing a suggestion
        # compares, and it keeps the rich comparisons out of the sort.
        self.suggestions = sorted(suggestions, key=_suspiciousness_of, reverse=True)

        suspiciousness: Dict[Location, float] = dict()
        current = suspiciousness.get
        for suggestion in self.suggestions:
            value = suggestion.suspiciousness
            for line in suggestion.lines:
                suspiciousness[line] = metric(
                    value, current(line, default_suspiciousness)
                )
        self.suspiciousness = suspiciousness

        groups: Dict[float, Set[Location]] = dict()
        for line, value in suspiciousness.items():
            lines = groups.get(value)
            if lines is None:
                groups[value] = {line}
            else:
                lines.add(line)
        self.suggestions_normalized = [
            Suggestion(list(lines), value)
            for value, lines in sorted(groups.items(), key=_key_of, reverse=True)
        ]

        self.ranks: Dict[float, List[Location]] = dict()
        self.locations: Dict[Location, float] = dict()
        self.effort: Dict[Location, int] = dict()
        locations = self.locations
        effort = self.effort
        current_rank = 1
        for suggestion in self.suggestions_normalized:
            lines = suggestion.lines
            size = len(lines)
            if size == 0:
                continue
            elif size == 1:
                rank = current_rank
                current_rank += 1
            else:
                rank = size / 2 + (current_rank - 1)
                current_rank += size
            self.ranks[rank] = lines
            value = suggestion.suspiciousness
            spent = current_rank - 1
            for line in lines:
                suspiciousness[line] = metric(
                    value, current(line, default_suspiciousness)
                )
                locations[line] = rank
                effort[line] = spent

        self.number_of_locations = total_number_of_locations or len(self.locations)
        self.default_rank = (self.number_of_locations - len(self.locations)) / 2 + (
            current_rank - 1
        )

    def _pool(self, n: int) -> List[Location]:
        """The locations a top-n draws from: the most suspicious ones first, each
        one only at the position where it was first seen."""
        pool = list()
        seen = set()
        for suggestion in self.suggestions:
            if len(pool) >= n:
                break
            for line in suggestion.lines:
                # A set for the membership test, a list for the order: the same
                # locations in the same order as testing against the list itself.
                if line not in seen:
                    seen.add(line)
                    pool.append(line)
        return pool

    def top_n(
        self,
        faulty: Set[Location],
        n: int,
        scenario: Optional[Scenario] = None,
        repeat: int = 1000,
    ) -> float:
        top_n_locations = self._pool(n)
        if len(top_n_locations) <= n:
            return self._top_n(faulty, top_n_locations, scenario)
        else:
            # Only the number of faulty locations in a draw decides the score, so
            # the pool is reduced to that flag up front. Drawing from the flags
            # consumes the random stream exactly like drawing from the locations
            # does, since random.sample looks at nothing but the population size.
            flags = [1 if line in faulty else 0 for line in top_n_locations]
            number_of_faulty = len(faulty)
            sample = random.sample
            score = self._score
            sum_ = 0
            for _ in range(repeat):
                sum_ += score(sum(sample(flags, k=n)), number_of_faulty, n, scenario)
            return sum_ / repeat

    @staticmethod
    def _score(
        found: int,
        number_of_faulty: int,
        number_of_locations: int,
        scenario: Optional[Scenario] = None,
    ) -> float:
        if scenario == Scenario.BEST_CASE:
            return 1 if found > 0 else 0
        elif scenario == Scenario.WORST_CASE:
            return found / number_of_faulty
        elif scenario == Scenario.AVG_CASE:
            return min(found / (number_of_faulty / 2), 1)
        else:
            return found / number_of_locations

    @staticmethod
    def _top_n(
        faulty: Set[Location],
        top_n_locations: List[Location],
        scenario: Optional[Scenario] = None,
    ) -> float:
        return Rank._score(
            len(faulty.intersection(top_n_locations)),
            len(faulty),
            len(top_n_locations),
            scenario,
        )

    @staticmethod
    def _aggregate(
        values: List[float], size: int, scenario: Optional[Scenario] = None
    ) -> float:
        if scenario == Scenario.BEST_CASE:
            return min(values)
        elif scenario == Scenario.WORST_CASE:
            return max(values)
        elif scenario == Scenario.AVG_CASE:
            values.sort()
            return values[max(size // 2 - 1, 0)]
        else:
            return sum(values) / size

    def get_rank(
        self, faulty: Set[Location], scenario: Optional[Scenario] = None
    ) -> float:
        rank_of = self.locations.get
        default_rank = self.default_rank
        return self._aggregate(
            [rank_of(location, default_rank) for location in faulty],
            len(faulty),
            scenario,
        )

    def exam(self, faulty: Set[Location], scenario: Optional[Scenario] = None) -> float:
        return self.get_rank(faulty, scenario) / self.number_of_locations

    def wasted_effort(
        self, faulty: Set[Location], scenario: Optional[Scenario] = None
    ) -> int:
        effort_of = self.effort.get
        default_effort = self.number_of_locations
        return self._aggregate(
            [effort_of(location, default_effort) for location in faulty],
            len(faulty),
            scenario,
        )
