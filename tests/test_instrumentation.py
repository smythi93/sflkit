import atexit
import os
import subprocess
from pathlib import Path

from sflkitlib.events import EventType

from sflkit import instrument_config, Config
from utils import BaseTest


class TestInstrumentation(BaseTest):
    def _test_complex_structure(self, config: Config):
        instrument_config(config)
        dst = Path(BaseTest.TEST_DIR)
        src = Path(BaseTest.TEST_RESOURCES, "test_instrumentation")
        main_py = dst / "main.py"
        exclude_py = dst / "exclude.py"
        file = dst / "file"
        exclude_file = dst / "exclude_file"
        exclude_dir = dst / "exclude_dir"
        exclude_dir_file = dst / "exclude_dir" / "file"
        package = dst / "package"
        package___init___py = dst / "package" / "__init__.py"
        package_exclude_py = dst / "package" / "exclude.py"
        package_test_py = dst / "package" / "test.py"

        src_main_py = src / "main.py"
        src_exclude_py = src / "exclude.py"
        src_file = src / "file"
        src_exclude_file = src / "exclude_file"
        src_exclude_dir_file = src / "exclude_dir" / "file"
        src_package___init___py = src / "package" / "__init__.py"
        src_package_exclude_py = src / "package" / "exclude.py"
        src_package_test_py = src / "package" / "test.py"

        exist_files = [
            main_py,
            exclude_py,
            file,
            exclude_file,
            exclude_dir_file,
            package___init___py,
            package_exclude_py,
            package_test_py,
        ]
        exist_dirs = [exclude_dir, package]

        for f in exist_files:
            self.assertTrue(f.exists())
            self.assertTrue(f.is_file())

        for d in exist_dirs:
            self.assertTrue(d.exists())
            self.assertTrue(d.is_dir())

        for d, s in [
            (exclude_py, src_exclude_py),
            (file, src_file),
            (exclude_file, src_exclude_file),
            (exclude_dir_file, src_exclude_dir_file),
            (package_exclude_py, src_package_exclude_py),
        ]:
            with open(d, "r") as fp:
                d_content = fp.read()
            with open(s, "r") as fp:
                s_content = fp.read()
            self.assertEqual(s_content, d_content, f"{d} has other content then {s}")

        for d, s in [
            (main_py, src_main_py),
            (package___init___py, src_package___init___py),
            (package_test_py, src_package_test_py),
        ]:
            with open(d, "r") as fp:
                d_content = fp.read()
            with open(s, "r") as fp:
                s_content = fp.read()
            self.assertNotEqual(
                s_content, d_content, f"{d} has the same content then {s}"
            )

    def test_complex_structure_exclude(self):
        self._test_complex_structure(
            Config.create(
                path=os.path.join(BaseTest.TEST_RESOURCES, "test_instrumentation"),
                language="python",
                events="line",
                predicates="line",
                working=BaseTest.TEST_DIR,
                exclude=r"exclude_dir,exclude\.py,excluded_file,"
                + os.path.join("package", r"exclude\.py"),
            )
        )

    def test_complex_structure_include(self):
        self._test_complex_structure(
            Config.create(
                path=os.path.join(BaseTest.TEST_RESOURCES, "test_instrumentation"),
                language="python",
                events="line",
                predicates="line",
                working=BaseTest.TEST_DIR,
                include=r"package,main\.py",
                exclude=os.path.join("package", r"exclude\.py"),
            )
        )

    def test_mapping_output(self):
        instrument_config(
            Config.create(
                path=os.path.join(BaseTest.TEST_RESOURCES, "test_instrumentation"),
                language="python",
                events="line",
                predicates="line",
                working=BaseTest.TEST_DIR,
                mapping_path="mapping.json",
            )
        )
        mapping = Path("mapping.json")
        self.assertTrue(mapping.exists())
        self.assertTrue(mapping.is_file())

    def test_instrument_exclude(self):
        src = Path(BaseTest.TEST_RESOURCES, "test_exclude")
        dst = Path(BaseTest.TEST_DIR)
        instrument_config(
            Config.create(
                path=str(src),
                language="python",
                events="line",
                predicates="line",
                working=BaseTest.TEST_DIR,
                include="included",
                exclude=os.path.join("included", "excluded"),
            )
        )
        included = dst / "included"
        excluded = included / "excluded"
        a = included / "a.py"
        b = excluded / "b.py"
        c = dst / "c.py"

        included_src = src / "included"
        excluded_src = included_src / "excluded"
        a_src = included_src / "a.py"
        b_src = excluded_src / "b.py"
        c_src = src / "c.py"

        self.assertTrue(included.exists())
        self.assertTrue(included.is_dir())
        self.assertTrue(excluded.exists())
        self.assertTrue(excluded.is_dir())
        self.assertTrue(a.exists())
        self.assertTrue(a.is_file())
        self.assertTrue(b.exists())
        self.assertTrue(b.is_file())
        self.assertTrue(c.exists())
        self.assertTrue(c.is_file())

        with open(a, "r") as fp:
            a_content = fp.read()
        with open(a_src, "r") as fp:
            a_src_content = fp.read()
        self.assertNotEqual(a_src_content, a_content)

        with open(b, "r") as fp:
            b_content = fp.read()
        with open(b_src, "r") as fp:
            b_src_content = fp.read()
        self.assertEqual(b_src_content, b_content)

        with open(c, "r") as fp:
            c_content = fp.read()
        with open(c_src, "r") as fp:
            c_src_content = fp.read()
        self.assertEqual(c_src_content, c_content)

    def test_instrument_with_tests(self):
        src = Path(BaseTest.TEST_RESOURCES, "test_runner")
        dst = Path(BaseTest.TEST_DIR)
        instrument_config(
            Config.create(
                path=str(src),
                language="python",
                events="line",
                predicates="line",
                test_events="test_line",
                working=BaseTest.TEST_DIR,
                tests="tests",
                mapping_path=BaseTest.TEST_MAPPING,
            )
        )
        tests = dst / "tests"
        middle_py = dst / "middle.py"
        test_middle_py = tests / "test_middle.py"

        tests_src = src / "tests"
        middle_py_src = src / "middle.py"
        test_middle_py_src = tests_src / "test_middle.py"

        self.assertTrue(tests.exists())
        self.assertTrue(tests.is_dir())
        self.assertTrue(middle_py.exists())
        self.assertTrue(middle_py.is_file())
        self.assertTrue(test_middle_py.exists())
        self.assertTrue(test_middle_py.is_file())

        with open(middle_py, "r") as fp:
            middle_content = fp.read()
        with open(middle_py_src, "r") as fp:
            middle_src_content = fp.read()
        self.assertNotEqual(middle_src_content, middle_content)
        self.assertIn("add_line_event", middle_content)
        self.assertNotIn("add_test_line_event", middle_content)

        with open(test_middle_py, "r") as fp:
            test_middle_content = fp.read()
        with open(test_middle_py_src, "r") as fp:
            test_middle_src_content = fp.read()
        self.assertNotEqual(test_middle_src_content, test_middle_content)
        self.assertIn("add_test_line_event", test_middle_content)
        self.assertNotIn("add_line_event", test_middle_content)


class TestLib(BaseTest):
    @classmethod
    def setUpClass(cls) -> None:
        from sflkitlib import lib

        atexit.unregister(lib.dump_events)
        cls.lib = lib
        cls.event_type_map = {
            EventType.DEF: lib.add_def_event,
            EventType.USE: lib.add_use_event,
            EventType.LINE: lib.add_line_event,
            EventType.BRANCH: lib.add_branch_event,
            EventType.CONDITION: lib.add_condition_event,
            EventType.LOOP_BEGIN: lib.add_loop_begin_event,
            EventType.LOOP_HIT: lib.add_loop_hit_event,
            EventType.LOOP_END: lib.add_loop_end_event,
            EventType.FUNCTION_ENTER: lib.add_function_enter_event,
            EventType.FUNCTION_EXIT: lib.add_function_exit_event,
            EventType.FUNCTION_ERROR: lib.add_function_error_event,
        }

    def setUp(self) -> None:
        self.events = None

    def tearDown(self) -> None:
        # noinspection PyBroadException
        try:
            os.remove(self.TEST_PATH)
        except:
            pass
        self.lib.reset()

    def test_get_id(self):
        x = 10
        self.assertEqual(id(x), self.lib.get_id(x))

    def test_get_type(self):
        x = 10
        self.assertEqual(type(x), self.lib.get_type(x))


class TestShadowedBuiltins(BaseTest):
    def test_instrumented_subject_survives_shadowed_builtins(self):
        """
        Instrumenting a subject that rebinds the builtins probes rely on must
        leave the subject runnable.

        The probes and their guards name builtins, and any scope they are
        injected into is free to bind those names to something else. When that
        happened the failure was not a wrong trace but no trace: the import of
        the package under test died, the test ran against uninstrumented code,
        and the run still exited zero.
        """
        config = Config.create(
            path=os.path.join(BaseTest.TEST_RESOURCES, "test_shadowed_builtins"),
            language="python",
            events=",".join(e.name for e in EventType.events()),
            working=BaseTest.TEST_DIR,
        )
        instrument_config(config)
        output = subprocess.run(
            [BaseTest.PYTHON, BaseTest.ACCESS],
            cwd=BaseTest.TEST_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertEqual(
            0,
            output.returncode,
            f"the instrumented subject did not run:\n{output.stdout}",
        )
        self.assertIn("2", output.stdout)
        self.assertIn("True", output.stdout)


class TestWhileWithContinue(BaseTest):
    def setUp(self):
        # Loop ids come from a counter on the factory class that instrumenting
        # never resets, and other tests assert on the ids they get. Instrumenting
        # a subject with loops here would shift theirs, so put the counter back.
        super().setUp()
        from sflkit.language.python.factory import LoopEventFactory

        self._loop_id = LoopEventFactory.loop_id
        self._loops = dict(LoopEventFactory.loops)

    def tearDown(self):
        from sflkit.language.python.factory import LoopEventFactory

        LoopEventFactory.loop_id = self._loop_id
        LoopEventFactory.loops = self._loops
        super().tearDown()

    def test_while_condition_is_refreshed_before_continue(self):
        """
        A ``continue`` must not strand the loop on a stale condition.

        The test of an instrumented ``while`` lives in a temporary so its value
        can be reported, refreshed at the end of the body -- which a
        ``continue`` jumps straight past. The loop then re-tests a value that
        can no longer change, and runs until something in the body raises.
        """
        config = Config.create(
            path=os.path.join(BaseTest.TEST_RESOURCES, "test_while_continue"),
            language="python",
            events=",".join(e.name for e in EventType.events()),
            working=BaseTest.TEST_DIR,
        )
        instrument_config(config)
        output = subprocess.run(
            [BaseTest.PYTHON, BaseTest.ACCESS],
            cwd=BaseTest.TEST_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            0,
            output.returncode,
            f"the instrumented loop did not terminate cleanly:\n{output.stdout}",
        )
        self.assertIn("['-pfoo', '-pbar']", output.stdout)
        self.assertIn("9", output.stdout)


class TestPropertyReentry(BaseTest):
    def setUp(self):
        super().setUp()
        from sflkit.language.python.factory import LoopEventFactory

        self._loop_id = LoopEventFactory.loop_id
        self._loops = dict(LoopEventFactory.loops)

    def tearDown(self):
        from sflkit.language.python.factory import LoopEventFactory

        LoopEventFactory.loop_id = self._loop_id
        LoopEventFactory.loops = self._loops
        super().tearDown()

    def test_probes_do_not_re_enter_a_property(self):
        """
        No probe may read an attribute that is a property.

        Reading it runs the property, and a probe inside that property re-enters
        it. The guard has to be on every probe that reports a variable, not just
        some: definition probes were fixed first and the length probe next to
        them still recursed, which aborts the interpreter rather than raising,
        so the probe's own ``try`` never sees it.
        """
        config = Config.create(
            path=os.path.join(BaseTest.TEST_RESOURCES, "test_property_reentry"),
            language="python",
            events=",".join(e.name for e in EventType.events()),
            working=BaseTest.TEST_DIR,
        )
        instrument_config(config)
        output = subprocess.run(
            [BaseTest.PYTHON, BaseTest.ACCESS],
            cwd=BaseTest.TEST_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            0,
            output.returncode,
            f"the instrumented subject did not survive its own probes:\n{output.stdout}",
        )
        self.assertIn("''", output.stdout)
        self.assertIn("0", output.stdout)


class TestStarredSubscript(BaseTest):
    def test_instrumented_source_keeps_pre_3_11_syntax(self):
        """
        The regenerated module must parse on the interpreter that runs it.

        Instrumentation happens on this interpreter; the subject's runs on its
        own, routinely older. ``x[(a, *b)]`` unparsed to ``x[a, *b]`` -- PEP 646
        syntax -- so the subject failed to import and every trace held nothing
        but that failure.
        """
        config = Config.create(
            path=os.path.join(BaseTest.TEST_RESOURCES, "test_starred_subscript"),
            language="python",
            events=",".join(e.name for e in EventType.events()),
            working=BaseTest.TEST_DIR,
        )
        instrument_config(config)
        instrumented = os.path.join(BaseTest.TEST_DIR, BaseTest.ACCESS)
        with open(instrumented) as handle:
            source = handle.read()
        # Ask the tree, not the text: the rewritten form contains the same
        # characters inside a call -- tuple([..., *indexer]) -- and only a
        # subscript whose slice is a starred tuple is the syntax at issue.
        import ast as _ast

        offenders = [
            node
            for node in _ast.walk(_ast.parse(source))
            if isinstance(node, _ast.Subscript)
            and isinstance(node.slice, _ast.Tuple)
            and any(isinstance(e, _ast.Starred) for e in node.slice.elts)
        ]
        self.assertEqual(
            [],
            offenders,
            "unparsing produced a subscript that needs Python 3.11 or newer",
        )
        output = subprocess.run(
            [BaseTest.PYTHON, BaseTest.ACCESS],
            cwd=BaseTest.TEST_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
        )
        self.assertEqual(0, output.returncode, output.stdout)
        self.assertIn("stored", output.stdout)


class TestGetattrProxy(BaseTest):
    def setUp(self):
        super().setUp()
        from sflkit.language.python.factory import LoopEventFactory

        self._loop_id = LoopEventFactory.loop_id
        self._loops = dict(LoopEventFactory.loops)

    def tearDown(self):
        from sflkit.language.python.factory import LoopEventFactory

        LoopEventFactory.loop_id = self._loop_id
        LoopEventFactory.loops = self._loops
        super().tearDown()

    def test_probes_do_not_re_enter_a_delegating_proxy(self):
        """
        No probe may read an attribute off a type that defines ``__getattr__``.

        A delegating proxy answers for names it does not carry by reading
        something else on itself, so one probe's read re-enters the proxy
        through another attribute. Nothing crashes: each probe's own ``try``
        swallows the resulting ``RecursionError`` and the run continues, but
        every level of the cycle emits its events. sphinx's
        ``_TranslationProxy`` filled nine traces with 37 million events apiece
        that covered eight files and reached the code under test in none.

        Guarding only against properties missed it -- the attribute a proxy is
        asked for is one its type does not define, so there is no property to
        find and the old guard let the read through.
        """
        events_path = os.path.join(BaseTest.TEST_DIR, "EVENTS")
        config = Config.create(
            path=os.path.join(BaseTest.TEST_RESOURCES, "test_getattr_proxy_bound"),
            language="python",
            events=",".join(e.name for e in EventType.events()),
            working=BaseTest.TEST_DIR,
        )
        instrument_config(config)
        output = subprocess.run(
            [BaseTest.PYTHON, BaseTest.ACCESS],
            cwd=BaseTest.TEST_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=120,
            env=dict(os.environ, EVENTS_PATH=events_path),
        )
        self.assertEqual(
            0,
            output.returncode,
            f"the instrumented subject did not survive its own probes:\n{output.stdout}",
        )
        # The proxy has to still resolve to what it resolved to uninstrumented.
        self.assertIn("HELLO", output.stdout)
        self.assertIn("hello", output.stdout)
        # The symptom was volume, not failure: this subject wrote a gigabyte
        # before the guard and tens of kilobytes after it.
        size = os.path.getsize(events_path) if os.path.exists(events_path) else 0
        self.assertLess(
            size,
            5_000_000,
            "the probes are still re-entering the proxy: the trace exploded",
        )
