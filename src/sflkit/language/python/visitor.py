import copy

from ast import *
from typing import Any, Union

from sflkit.language.meta import MetaVisitor, Injection
from sflkit.language.python.extract import PythonIsDoc
from sflkit.language.python.factory import (
    python_builtins,
    python_builtins_module,
    python_lib,
    python_lib_module,
)
from sflkit.language.visitor import ASTVisitor


def _refresh_before_continue(body: list, refresh: list) -> list:
    """
    Re-evaluate a ``while`` test before every ``continue`` that belongs to it.

    A ``while`` keeps its test in a temporary so the condition's value can be
    reported, and the temporary is refreshed at the end of the body. A
    ``continue`` jumps straight past that refresh, so the loop goes on testing
    the value the condition had an iteration ago -- which never changes again,
    making the loop run until something inside it raises. pytest's
    ``consider_preparse`` is one such loop: it walks ``args`` with a
    ``continue`` in the common case, so instrumented pytest ran off the end of
    the list and died before it could run a single test.

    Nested loops are left alone -- their own ``continue`` belongs to them --
    and so are nested function and class bodies.

    :param body: Statements of the loop body.
    :param refresh: Statements that recompute the loop's test.
    :returns: The body with the refresh inserted ahead of each ``continue``.
    """
    result = []
    for statement in body:
        if isinstance(statement, Continue):
            result.extend(copy.deepcopy(refresh))
            result.append(statement)
            continue
        if isinstance(
            statement,
            (For, AsyncFor, While, FunctionDef, AsyncFunctionDef, ClassDef),
        ):
            result.append(statement)
            continue
        for field in ("body", "orelse", "finalbody"):
            nested = getattr(statement, field, None)
            if isinstance(nested, list):
                setattr(statement, field, _refresh_before_continue(nested, refresh))
        for handler in getattr(statement, "handlers", []) or []:
            handler.body = _refresh_before_continue(handler.body, refresh)
        result.append(statement)
    return result


class _StarredSubscripts(NodeTransformer):
    """
    Rewrite ``x[(a, *b)]`` so it survives being unparsed for an older Python.

    ``ast.unparse`` drops the parentheses and emits ``x[a, *b]``, which is only
    syntax from Python 3.11 (PEP 646). Instrumentation runs on this
    interpreter but the rewritten sources run on the subject's, which is
    routinely 3.8 or 3.9: xarray's ``variable.py`` came back with a
    ``SyntaxError``, so importing xarray failed and every trace for the
    instance held nothing but the failed import.

    Building the tuple explicitly says the same thing in syntax every version
    accepts. ``tuple`` is reached through the tracer's builtins alias because
    the subject is free to rebind the bare name.
    """

    def visit_Subscript(self, node: Subscript) -> AST:
        self.generic_visit(node)
        index = node.slice
        if isinstance(index, Tuple) and any(
            isinstance(element, Starred) for element in index.elts
        ):
            node.slice = Call(
                func=Attribute(
                    value=Name(id=python_builtins, ctx=Load()),
                    attr="tuple",
                    ctx=Load(),
                ),
                args=[List(elts=index.elts, ctx=Load())],
                keywords=[],
            )
        return node


class PythonInstrumentation(NodeTransformer, ASTVisitor):
    def __init__(self, meta_visitor: MetaVisitor):
        super().__init__(meta_visitor)
        self.is_doc = PythonIsDoc()
        self.__future__ = list()

    def parse(self, source: str):
        return parse(source)

    def start_visit(self, ast):
        self.__future__ = list()
        if isinstance(ast, Module) and ast.body and self.is_doc.visit(ast.body[0]):
            doc = [ast.body[0]]
            ast.body = ast.body[1:]
        else:
            doc = list()
        instrumented_tree = self.visit(ast)
        instrumented_tree = _StarredSubscripts().visit(instrumented_tree)
        return Module(
            body=doc
            + self.__future__
            + [
                Import(names=[alias(name=python_lib_module, asname=python_lib)]),
                # Probe guards catch the builtin exception through this module
                # rather than by the bare name, which the subject is free to
                # rebind -- see get_exception_type().
                Import(
                    names=[
                        alias(name=python_builtins_module, asname=python_builtins)
                    ]
                ),
                instrumented_tree,
            ],
            type_ignores=list(),
        )

    def unparse(self, ast):
        return unparse(ast)

    def __create_node(self, injection: Injection, node: AST, body=False, doc=None):
        doc = doc if doc else list()
        if injection.body:
            node.body = injection.body + node.body
        if injection.body_last:
            if isinstance(node, While):
                node.body = _refresh_before_continue(node.body, injection.body_last)
            node.body += injection.body_last
        if injection.orelse:
            node.orelse = injection.orelse + node.orelse
        if injection.assign:
            if hasattr(node, "value"):
                node.value = injection.assign
            elif hasattr(node, "test"):
                node.test = injection.assign
        if injection.finalbody:
            if hasattr(node, "finalbody"):
                node.finalbody = injection.finalbody + node.finalbody
            else:
                if body:
                    node.body = [
                        Try(
                            body=node.body,
                            handlers=[],
                            orelse=[],
                            finalbody=injection.finalbody,
                        )
                    ]
                else:
                    node = Try(
                        body=[node],
                        handlers=[],
                        orelse=[],
                        finalbody=injection.finalbody,
                    )
        if injection.error:
            error_var = self.meta_visitor.tmp_generator.get_var_name()
            raise_stmt = [
                Raise(
                    exc=Name(id=error_var),
                    cause=None,
                )
            ]
            if body:
                node.body = [
                    Try(
                        body=node.body,
                        handlers=[
                            ExceptHandler(
                                type=Name(
                                    id="BaseException",
                                ),
                                name=error_var,
                                body=injection.error + raise_stmt,
                            )
                        ],
                        orelse=[],
                        finalbody=[],
                    )
                ]
            else:
                node = Try(
                    body=[node],
                    handlers=[
                        ExceptHandler(
                            type=Name(
                                id="BaseException",
                            ),
                            name=error_var,
                            body=injection.error + raise_stmt,
                        )
                    ],
                    orelse=[],
                    finalbody=[],
                )
        if doc and hasattr(node, "body"):
            node.body = doc + node.body
        if injection.pre or injection.post:
            return Module(
                body=injection.pre + [node] + injection.post,
                type_ignores=list(),
            )
        return node

    def __visit_function(self, node: Union[FunctionDef, AsyncFunctionDef]) -> AST:
        self.meta_visitor.enter_function(node)
        injection = self.meta_visitor.visit_start(node)
        if self.is_doc.visit(node.body[0]):
            doc = [node.body[0]]
            body = node.body[1:]
        else:
            doc = None
            body = node.body
        node.body = [self.visit(n) for n in body]
        self.meta_visitor.exit_function(node)
        self.events += injection.events
        return self.__create_node(injection, node, body=True, doc=doc)

    def visit_FunctionDef(self, node: FunctionDef) -> AST:
        return self.__visit_function(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> AST:
        return self.__visit_function(node)

    def visit_ClassDef(self, node: ClassDef) -> AST:
        self.meta_visitor.enter_class(node)
        injection = self.meta_visitor.visit_start(node)
        if self.is_doc.visit(node.body[0]):
            doc = [node.body[0]]
            body = node.body[1:]
        else:
            doc = None
            body = node.body
        node.body = [self.visit(n) for n in body]
        self.meta_visitor.exit_class(node)
        self.events += injection.events
        return self.__create_node(injection, node, doc=doc)

    def generic_visit(self, node: AST) -> AST:
        injection = self.meta_visitor.visit_start(node)
        self.events += injection.events
        super().generic_visit(node)
        return self.__create_node(injection, node)

    def _visit_import(self, node: Union[Import, ImportFrom]):
        if any(
            alias_.name == "__future__" for alias_ in node.names
        ):  # ignore __future__
            self.__future__.append(node)
            return
        return self.generic_visit(node)

    def visit_Import(self, node: Import) -> Any:
        return self._visit_import(node)

    def visit_ImportFrom(self, node: ImportFrom) -> Any:
        if node.module == "__future__":  # ignore __future__
            self.__future__.append(node)
            return
        return self._visit_import(node)
