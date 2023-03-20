import os
import subprocess
import unittest

from sflkit import instrument_config
from sflkit.config import Config
from sflkit.events import event

test_resources = os.path.join("resources", "subjects", "tests")
test_dir = "test_dir"
test_events = "test_events.json"
test_path = "EVENTS_PATH"
python = "python3.10"
access = "main.py"


class EventTests(unittest.TestCase):
    def test_lines(self):
        config = Config.config(
            path=os.path.join(test_resources, "test_lines"),
            language="python",
            events="line",
            working=test_dir,
        )
        instrument_config(config)

        subprocess.run([python, access], cwd=test_dir)

        events = event.load(os.path.join(test_dir, test_path))
        self.assertEqual(3, len(events))
        for i, e in enumerate(events):
            self.assertIsInstance(e, event.LineEvent, f"{e} is not a line event")
            self.assertEqual(e.file, access, f"{e} has not correct file")
            self.assertEqual(e.line, i + 1, f"{e} has not correct line")

    def test_branches(self):
        config = Config.config(
            path=os.path.join(test_resources, "test_branches"),
            language="python",
            events="line,branch",
            working=test_dir,
        )
        instrument_config(config)

        subprocess.run([python, access], cwd=test_dir)

        events = event.load(os.path.join(test_dir, test_path))
        self.assertEqual(5, len(events))
        lines = [1, 4, 5]
        line_i = 0
        first_branch = True
        branch_lines = [1, 4]
        branch_i = 0
        for e in events:
            if e.event_type == event.EventType.LINE:
                self.assertIsInstance(e, event.LineEvent, f"{e} is not a line event")
                self.assertEqual(e.file, access, f"{e} has not correct file")
                self.assertEqual(e.line, lines[line_i], f"{e} has not correct line")
                line_i += 1
            elif e.event_type == event.EventType.BRANCH:
                self.assertIsInstance(
                    e, event.BranchEvent, f"{e} is not a condition event"
                )
                self.assertEqual(e.file, access, f"{e} has not correct file")
                self.assertEqual(
                    e.line, branch_lines[branch_i], f"{e} has not correct line"
                )
                if first_branch:
                    self.assertGreater(
                        e.then_id, e.else_id, f"{e} has not correct branch ids"
                    )
                else:
                    self.assertLess(
                        e.then_id, e.else_id, f"{e} has not correct branch ids"
                    )
                first_branch = False
                branch_i += 1

    @staticmethod
    def _test_events(events):
        config = Config.config(
            path=os.path.join(test_resources, "test_events"),
            language="python",
            events=events,
            working=test_dir,
        )
        instrument_config(config)

        subprocess.run([python, access], cwd=test_dir)
        return event.load(os.path.join(test_dir, test_path))

    def test_function(self):
        events = self._test_events("function_enter,function_exit")
        self.assertEqual(20, len(events))
        function_enter = list(
            zip(
                [9, 2, 5, 5, 5, 5, 5, 9, 2, 5],
                ["a", "__init__", "a", "a", "a", "a", "a", "a", "__init__", "a"],
            )
        )
        function_enter_i = 0
        function_exit = list(
            zip(
                [2, 6, 6, 6, 6, 6, 13, 2, 6, 13],
                ["__init__", "a", "a", "a", "a", "a", "a", "__init__", "a", "a"],
                [None, 8, 12, 16, 20, 24, 24, None, 2, 2],
            )
        )
        function_exit_i = 0
        for e in events:
            if e.event_type == event.EventType.FUNCTION_ENTER:
                line, function = function_enter[function_enter_i]
                self.assertIsInstance(
                    e, event.FunctionEnterEvent, f"{e} is not a line event"
                )
                self.assertEqual(access, e.file, f"{e} has not correct file")
                self.assertEqual(line, e.line, f"{e} has not correct line")
                self.assertEqual(function, e.function, f"{e} has not correct function")
                function_enter_i += 1
            elif e.event_type == event.EventType.FUNCTION_EXIT:
                line, function, value = function_exit[function_exit_i]
                self.assertIsInstance(
                    e, event.FunctionExitEvent, f"{e} is not a line event"
                )
                self.assertEqual(access, e.file, f"{e} has not correct file")
                self.assertEqual(line, e.line, f"{e} has not correct line")
                self.assertEqual(function, e.function, f"{e} has not correct function")
                self.assertEqual(value, e.return_value, f"{e} has not correct function")
                function_exit_i += 1

    def test_branch(self):
        events = self._test_events("branch")
        self.assertEqual(10, len(events))
        branches = list(
            zip(
                [11, 11, 11, 11, 11, 11, 11, 11, 16, 23],
                [-1, -1, -1, -1, -1, 1, -1, 1, -1, 0],
            )
        )
        branches_i = 0
        for e in events:
            if e.event_type == event.EventType.BRANCH:
                line, mod = branches[branches_i]
                self.assertIsInstance(e, event.BranchEvent, f"{e} is not a line event")
                self.assertEqual(access, e.file, f"{e} has not correct file")
                self.assertEqual(line, e.line, f"{e} has not correct line")
                if mod < 0:
                    self.assertLess(
                        e.then_id, e.else_id, f"{e} has not correct branch ids"
                    )
                elif mod > 0:
                    self.assertGreater(
                        e.then_id, e.else_id, f"{e} has not correct branch ids"
                    )
                else:
                    self.assertEqual(-1, e.else_id, f"{e} has not correct branch ids")
                    self.assertLessEqual(
                        0, e.then_id, f"{e} has not correct branch ids"
                    )
                branches_i += 1

    def test_loop(self):
        events = self._test_events("loop_begin,loop_hit,loop_end")
        self.assertEqual(10, len(events))
        expected_loop = [
            (event.EventType.LOOP_BEGIN, 11),
            (event.EventType.LOOP_HIT, 11),
            (event.EventType.LOOP_HIT, 11),
            (event.EventType.LOOP_HIT, 11),
            (event.EventType.LOOP_HIT, 11),
            (event.EventType.LOOP_HIT, 11),
            (event.EventType.LOOP_END, 11),
            (event.EventType.LOOP_BEGIN, 11),
            (event.EventType.LOOP_HIT, 11),
            (event.EventType.LOOP_END, 11),
        ]
        for e, expected in zip(events, expected_loop):
            type_, line = expected
            self.assertEqual(e.event_type, type_, f"{e} is not of type {type_}")
            self.assertIsInstance(
                e,
                event.event_mapping[type_],
                f"{e} is not a {event.event_mapping[type_]}",
            )
            self.assertEqual(access, e.file, f"{e} has not correct file")
            self.assertEqual(line, e.line, f"{e} has not correct line")
            self.assertEqual(0, e.loop_id, f"{e} has not correct loop id")

    def test_def_use(self):
        events = self._test_events("def,use")
        loop = [
            # loop
            (event.EventType.DEF, 11, "i", None),
            (event.EventType.USE, 12, "b", None),
            # A.a
            (event.EventType.DEF, 5, "b", None),
            (event.EventType.USE, 6, ["b", "self.b"], None),
            (event.EventType.USE, 6, ["b", "self.b"], None),
            (event.EventType.DEF, 12, "d.b", None),
            (event.EventType.USE, 11, "c", None),
        ]

        def get_a(b, c, result):
            return (
                [
                    # a
                    (event.EventType.DEF, 9, ["b", "c"], [b, c]),
                    (event.EventType.DEF, 9, ["b", "c"], [b, c]),
                    (event.EventType.USE, 10, "b", None),
                    # A.__init__
                    (event.EventType.DEF, 2, "b", b),
                    (event.EventType.USE, 3, "b", None),
                    (event.EventType.DEF, 3, "self.b", b),
                    (event.EventType.DEF, 10, "d", None),
                    (event.EventType.USE, 11, "c", None),
                ]
                + loop * c
                + [
                    (event.EventType.USE, 13, "d.b", result),
                ]
            )

        expected_def_uses = get_a(4, 5, 24) + get_a(1, 1, 2)
        self.assertEqual(len(expected_def_uses), len(events))  # defs + uses
        for e, expected in zip(events, expected_def_uses):
            type_, line, var, val = expected
            self.assertEqual(type_, e.event_type, f"{e} is not of type {type_}")
            self.assertIsInstance(
                e,
                event.event_mapping[type_],
                f"{e} is not a {event.event_mapping[type_]}",
            )
            self.assertEqual(access, e.file, f"{e} has not correct file")
            self.assertEqual(line, e.line, f"{e} has not correct line")
            if isinstance(var, list):
                self.assertIn(e.var, var, f"{e} has not correct var")
            else:
                self.assertEqual(var, e.var, f"{e} has not correct var")
            if type_ == event.EventType.DEF and val:
                if isinstance(val, list):
                    self.assertIn(e.value, val, f"{e} has not correct value")
                else:
                    self.assertEqual(val, e.value, f"{e} has not correct value")

    def test_condition(self):
        events = self._test_events("condition")
        self.assertEqual(3, len(events))
        expected_conditions = [
            (event.EventType.CONDITION, 16, True, "a(4, 5)"),
            (event.EventType.CONDITION, 16, True, "a(1, 1)"),
            (event.EventType.CONDITION, 16, True, "a(4, 5) and a(1, 1)"),
        ]
        for e, expected in zip(events, expected_conditions):
            type_, line, ev, exp = expected
            self.assertEqual(e.event_type, type_, f"{e} is not of type {type_}")
            self.assertIsInstance(
                e,
                event.event_mapping[type_],
                f"{e} is not a {event.event_mapping[type_]}",
            )
            self.assertEqual(access, e.file, f"{e} has not correct file")
            self.assertEqual(line, e.line, f"{e} has not correct line")
            self.assertEqual(ev, e.value, f"{e} has not correct value")
            self.assertEqual(exp, e.condition, f"{e} has not correct condition")
