import ast
import unittest

import jast

from sflkit.language.java.extract import JavaVarExtract
from sflkit.language.python.extract import PythonVarExtract


class VarExtractionTest(unittest.TestCase):
    def _test_extract(self, expr: str, ins, outs, use=True):
        visitor = PythonVarExtract(use=use)
        tree = ast.parse(expr)
        variables = visitor.visit(tree)
        for i in ins:
            self.assertIn(i, variables)
        for o in outs:
            self.assertNotIn(o, variables)

    def test_generator(self):
        self._test_extract("[d for d in ds]", ["ds"], ["d"])
        self._test_extract("[d for d in ds if any(r for r in ds)]", ["ds"], ["d", "r"])
        self._test_extract(
            "[d + r for d in ds if any(r for r in ds)]", ["ds", "r"], ["d"]
        )
        self._test_extract(
            '[d for d in ds if d.name == "test"]', ["ds", "d.name"], ["d"]
        )
        self._test_extract("(d for d in ds)", ["ds"], ["d"])
        self._test_extract("(d for d in ds if any(r for r in ds))", ["ds"], ["d", "r"])
        self._test_extract(
            "(d + r for d in ds if any(r for r in ds))", ["ds", "r"], ["d"]
        )
        self._test_extract(
            '(d for d in ds if d.name == "test")', ["ds"], ["d", "d.name"]
        )
        self._test_extract("{d for d in ds}", ["ds"], ["d"])
        self._test_extract("{d for d in ds if any(r for r in ds)}", ["ds"], ["d", "r"])
        self._test_extract(
            "{d + r for d in ds if any(r for r in ds)}", ["ds", "r"], ["d"]
        )
        self._test_extract(
            '{d for d in ds if d.name == "test"}', ["ds"], ["d", "d.name"]
        )

    def test_lambda(self):
        self._test_extract("lambda d: d + r", ["r"], ["d"])
        self._test_extract("lambda d: d.name", ["d.name"], ["d"])

    def test_arguments(self):
        self._test_extract("def f(x=y):\n    pass", ["x"], ["y"], use=False)
        self._test_extract("f(x=y)", ["y"], ["x"])

    def test_attribute(self):
        self._test_extract("x.y", ["x", "x.y"], ["y"])
        self._test_extract("x.y.z", ["x", "x.y", "x.y.z"], ["y", "z", "y.z", "x.z"])
        self._test_extract("x.y", ["x.y"], ["x", "y"], use=False)
        self._test_extract("x.y.z", ["x.y.z"], ["x", "x.y", "y", "z", "y.z", "x.z"], use=False)
        self._test_extract(
            "x.f().z", ["x", "x.f"], ["f()", "z", "x.f()", "x.f().z", "f().z"]
        )


class JavaVarExtractionTest(unittest.TestCase):
    def _test_extract(self, expr: str, ins, outs, use=True, mode=jast.ParseMode.EXPR):
        visitor = JavaVarExtract(use=use)
        tree = jast.parse(expr, mode=mode)
        variables = visitor.visit(tree)
        for i in ins:
            self.assertIn(i, variables)
        for o in outs:
            self.assertNotIn(o, variables)

    def test_lambda(self):
        self._test_extract("d -> d + r", ["r"], ["d"])
        self._test_extract("d -> d.name", [], ["d", "d.name"])

    def test_arguments(self):
        self._test_extract(
            "int f(int x){}", ["x"], [], use=False, mode=jast.ParseMode.DECL
        )
        self._test_extract("x = f(y)", ["y"], ["x"])

    def test_assign(self):
        self._test_extract("x = y", ["y"], ["x"])
        self._test_extract("x = y + z", ["y", "z"], ["x"])
        self._test_extract("x = y", ["x"], ["y"], use=False)
        self._test_extract("x = y + z", ["x"], ["y", "z"], use=False)
        self._test_extract("x[y] = z", ["y", "z"], ["x"])
        self._test_extract("x[y] = z", ["x"], ["y", "z"], use=False)

    def test_attribute(self):
        self._test_extract("x.y", ["x", "x.y"], ["y"])
        self._test_extract("x.y.z", ["x", "x.y", "x.y.z"], ["y", "z", "y.z"])
        self._test_extract("x.y", ["x.y"], ["x", "y"], use=False)
        self._test_extract("x.y.z", ["x.y.z"], ["x", "x.y", "y", "z", "y.z"], use=False)
        self._test_extract(
            "x.f().z", ["x"], ["f()", "z", "x.f", "x.f()", "x.f().z", "f().z", "x.z"]
        )
