from contextlib import contextmanager
from functools import reduce
from typing import List

from sortedcollections import OrderedSet

from sflkit.language.extract import VariableExtract, ConditionExtract
import jast

from sflkitlib.events.event import ConditionEvent


class JavaVarExtract(jast.JNodeVisitor, VariableExtract):
    def __init__(self, use=False):
        self.use = use
        self.current_ignores = set()
        self.ignores = list()
        self.subscript = False

    @contextmanager
    def ignore(self):
        self.ignores.append(self.current_ignores)
        self.current_ignores = set(self.current_ignores)
        yield
        self.current_ignores = self.ignores.pop()

    @contextmanager
    def ignore_except_subscript(self):
        self.subscript = True
        yield
        self.subscript = False

    @contextmanager
    def include(self):
        self.subscript, old_subscript = False, self.subscript
        yield
        self.subscript = old_subscript

    def default_result(self):
        return OrderedSet()

    def aggregate_result(self, aggregate, result):
        return aggregate | result

    def generic_visit(self, node):
        # None (optional/empty child slots) and literal leaves
        # (CharLiteral/StringLiteral/IntLiteral/...) subclass str/int, so jast's
        # generic_visit would try to iterate them and fail.  None of these hold
        # variables.
        if node is None or isinstance(node, (str, int)):
            return self.default_result()
        return super().generic_visit(node)

    def visit_list(self, node: List[jast.JAST]):
        return reduce(
            self.aggregate_result, map(self.visit, node), self.default_result()
        )

    def visit_params(self, node):
        return self.visit(node.parameters)

    def visit_param(self, node: jast.param):
        return self.visit(node.id)

    def visit_arity(self, node):
        return self.visit(node.id)

    def visit_variabledeclaratorid(self, node: jast.variabledeclaratorid):
        if self.subscript:
            return self.default_result()
        return OrderedSet([str(node.id)])

    def visit_Lambda(self, node: jast.Lambda):
        if self.subscript:
            return self.default_result()
        with self.ignore():
            if node.args:
                if isinstance(node.args, jast.identifier):
                    self.current_ignores.update({node.args.value})
                elif isinstance(node.args, jast.params):
                    self.current_ignores.update(self.visit(node.args))
                else:
                    self.current_ignores.update({arg.value} for arg in node.args)
            return self.visit(node.body) - self.current_ignores

    def visit_Assign(self, node: jast.Assign):
        if self.subscript:
            return self.default_result()
        if self.use:
            with self.ignore_except_subscript():
                variables = self.visit(node.target)
            return variables | self.visit(node.value)
        else:
            return self.visit(node.target)

    def visit_InstanceOf(self, node: jast.InstanceOf):
        if self.subscript:
            return self.default_result()
        return self.visit(node.value)

    def visit_Cast(self, node: jast.Cast):
        return self.visit(node.value)

    def visit_NewObject(self, node: jast.NewObject):
        return self.visit(node.args)

    def visit_NewArray(self, node: jast.NewArray):
        return self.visit(node.expr_dims) | self.visit(node.init)

    def visit_SwitchExp(self, node: jast.SwitchExp):
        return self.visit(node.value)

    def visit_Constant(self, node):
        return self.default_result()

    @staticmethod
    def _is_type_name(name) -> bool:
        # By Java convention a type's first letter is uppercase (e.g. System,
        # Integer).  Ignore leading '$'/'_' as used in generated or internal
        # class names (e.g. Gson's `$Gson$Types`, `$Gson$Preconditions`).
        return str(name).lstrip("$_")[:1].isupper()

    def visit_Name(self, node: jast.Name):
        if self.subscript:
            return self.default_result()
        name = str(node.id)
        # Skip type/class references: a bare identifier that names a type is not
        # a value, so it must not be passed to JLib.getID(...).  This also drops
        # static accesses rooted at a type (e.g. System.out, $Gson$Types.x),
        # which are not local data flow and would otherwise not compile.
        if self._is_type_name(name):
            return self.default_result()
        return OrderedSet([name])

    def visit_ClassExpr(self, node):
        return self.default_result()

    def visit_ExplicitGenericInvocation(self, node):
        return self.default_result()

    def visit_Subscript(self, node):
        variables = self.visit(node.value)
        if self.use:
            with self.include():
                return variables | self.visit(node.index)
        return variables

    def check_Member(self, node):
        if isinstance(node, jast.Member):
            if isinstance(node.member, jast.Name):
                if isinstance(node.value, jast.Name):
                    return True
                return self.check_Member(node.value)
            return False
        return False

    @staticmethod
    def _dotted_name(node):
        """Full dotted path of a pure ``Name(.Name)*`` chain, else ``None``."""
        if isinstance(node, jast.Name):
            return str(node.id)
        if isinstance(node, jast.Member) and isinstance(node.member, jast.Name):
            base = JavaVarExtract._dotted_name(node.value)
            return None if base is None else f"{base}.{node.member.id}"
        return None

    def visit_Member(self, node):
        if not isinstance(node.member, jast.Name):
            return self.visit(node.value)
        # A segment that names a type (e.g. `pkg.Type`, `obj.Type.X`): the whole
        # qualified reference names a type or a static member, not local data
        # flow, so it must not be passed to JLib.getID(...).  Drop it (mirrors
        # the rule in visit_Name).
        if self._is_type_name(node.member.id):
            return self.default_result()
        variables = self.visit(node.value)
        # Only extend the *full* name of the receiver (e.g. `a.b` -> `a.b.c`),
        # and only when that receiver is itself a recognized value.  Extending
        # every sub-prefix would fabricate names like `a.c` (or, for qualified
        # names, mangle package segments such as `org.commons`).
        if self.check_Member(node):
            parent = self._dotted_name(node.value)
            if parent is not None and parent in variables and parent not in self.current_ignores:
                extended = OrderedSet([f"{parent}.{node.member.id}"])
                return (variables | extended) if self.use else extended
        return variables

    def visit_Call(self, node):
        return self.visit(node.args)

    def visit_declarator(self, node):
        if self.use and node.init:
            return self.visit(node.init)
        return self.default_result()


class JavaConditionExtract(jast.JNodeVisitor, ConditionExtract):
    def __init__(self):
        self.factory = None
        self.file = None

    def setup(self, factory):
        self.file = factory.file
        self.factory = factory

    def __get_tmp_var(self, val: jast.expr, expression: str):
        var = self.factory.tmp_generator.get_var_name()
        e = ConditionEvent(
            self.file,
            val.lineno,
            self.factory.event_id_generator.get_next_id(),
            expression,
            tmp_var=var,
        )
        return (
            var,
            jast.Name(id=var),
            jast.Compound(
                body=[
                    jast.LocalVariable(
                        type=jast.Boolean(),
                        declarators=[
                            jast.declarator(
                                id=jast.variabledeclaratorid(id=var),
                                init=val,
                            )
                        ],
                    ),
                    self.factory.get_event_call(e),
                ]
            ),
            [e],
        )

    def generic_visit(self, node):
        return self.__get_tmp_var(node, jast.unparse(node))

    def __assign_var(self, var, value):
        return jast.Expr(value=jast.Assign(target=jast.Name(id=var), value=value))

    @staticmethod
    def contains_assign(node):
        # whether the expression assigns a variable (e.g. `(x = f()) == 0`)
        if isinstance(node, jast.Assign):
            return True
        if isinstance(node, jast.JAST):
            for _, value in node:
                if isinstance(value, list):
                    if any(
                        JavaConditionExtract.contains_assign(item)
                        for item in value
                        if isinstance(item, jast.JAST)
                    ):
                        return True
                elif isinstance(
                    value, jast.JAST
                ) and JavaConditionExtract.contains_assign(value):
                    return True
        return False

    def visit_BinOp(self, node):
        if not isinstance(node.op, (jast.And, jast.Or)):
            return self.generic_visit(node)
        is_and = isinstance(node.op, jast.And)
        var_l, use_l, assign_l, e_l = self.visit(node.left)
        var_r, use_r, assign_r, e_r = self.visit(node.right)

        final_var = self.factory.tmp_generator.get_var_name()
        event = ConditionEvent(
            self.file,
            node.lineno,
            self.factory.event_id_generator.get_next_id(),
            jast.unparse(node),
            tmp_var=final_var,
        )
        # Short-circuit desugaring that keeps the right operand's temporaries in
        # scope: declare the result once, evaluate the right side (and assign the
        # result) only on the non-short-circuiting branch.
        #   &&:  if (left)  { <eval right>; final = right; } else { final = false; }
        #   ||:  if (!left) { <eval right>; final = right; } else { final = true;  }
        test = use_l if is_and else jast.UnaryOp(op=jast.Not(), operand=use_l)
        short_value = jast.Constant(jast.BoolLiteral(not is_and))
        branch = jast.If(
            test=test,
            body=jast.Block(body=[assign_r, self.__assign_var(final_var, use_r)]),
            orelse=jast.Block(body=[self.__assign_var(final_var, short_value)]),
        )
        assign = jast.Compound(
            body=[
                assign_l,
                jast.LocalVariable(
                    type=jast.Boolean(),
                    declarators=[
                        jast.declarator(id=jast.variabledeclaratorid(id=final_var))
                    ],
                ),
                branch,
                self.factory.get_event_call(event),
            ]
        )
        return final_var, jast.Name(id=final_var), assign, e_l + e_r + [event]

    def visit_UnaryOp(self, node):
        if isinstance(node.op, jast.Not):
            var, use, assign, e_o = self.visit(node.operand)
            expression = jast.unparse(node)
            final_var, final_use, final_assign, e = self.__get_tmp_var(
                jast.UnaryOp(op=node.op, operand=use, lineno=node.lineno), expression
            )
            return (
                final_var,
                final_use,
                jast.Compound(body=[assign, final_assign]),
                e_o + e,
            )
        else:
            return self.generic_visit(node)

    def visit_Expression(self, node):
        return self.visit(node.value)


class ReturnFinder(jast.JNodeVisitor):
    def default_result(self):
        return False

    def aggregate_result(self, aggregate, result):
        return aggregate or result

    def visit_Return(self, node):
        return True
