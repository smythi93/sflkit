import unittest

from sflkit.model.scope import Var, Scope


class TestScope(unittest.TestCase):
    def test_var_eq(self):
        var_1 = Var("x", 2, int)
        var_2 = Var("y", 2, int)
        var_3 = Var("x", "", str)
        self.assertEqual(var_1, var_3)
        self.assertNotEqual(var_1, var_2)
        self.assertNotEqual(var_2, var_3)
        self.assertEqual(hash(var_1), hash(var_3))
        self.assertNotEqual(hash(var_1), hash(var_2))
        self.assertNotEqual(hash(var_2), hash(var_3))

    def test_scope_without_parent(self):
        scope = Scope()
        self.assertIs(scope, scope.exit())

    def test_scope_with_parent(self):
        parent_scope = Scope()
        child_scope = parent_scope.enter()
        self.assertIs(parent_scope, child_scope.exit())

    def test_scope_contains(self):
        scope = Scope()
        scope.variables["x"] = Var("x", 10, int)
        self.assertIn("x", scope)
        self.assertNotIn("y", scope)
