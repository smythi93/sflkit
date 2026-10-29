import os
from typing import Set

import jast

from sflkit.language.finder import (
    LocationsFinder,
    FunctionFinder,
    LoopFinder,
    BranchFinder,
)


class JavaLocationsFinder(jast.JNodeVisitor, LocationsFinder):
    def get_locations(self, base_dir: str):
        if os.path.isfile(base_dir):
            base_dir = ""
        with open(os.path.join(base_dir, self.file), "r") as fp:
            s = fp.read()
        tree = jast.parse(s)
        self.visit(tree)
        return sorted(list(self.lines))

    def default_result(self) -> Set[int]:
        return set()

    def aggregate_result(self, aggregate: Set[int], result: Set[int]) -> Set[int]:
        return aggregate | result

    def generic_visit(self, node: jast.JAST) -> Set[int]:
        if getattr(node, "lineno", None) is not None:
            lines = {node.lineno}
        else:
            lines = set()
        for _, value in node:
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, jast.JAST):
                        lines |= self.visit(item)
            elif isinstance(value, jast.JAST):
                lines |= self.visit(value)
        return lines


class JavaFunctionFinder(JavaLocationsFinder, FunctionFinder):
    def visit_function(self, node) -> Set[int]:
        if node.lineno == self.line and node.id.value == self.target:
            lines = set(range(node.lineno, node.end_lineno + 1))
            self.lines |= lines
            return lines
        return self.generic_visit(node)

    def visit_Method(self, node: jast.Method) -> Set[int]:
        return self.visit_function(node)

    def visit_Constructor(self, node: jast.Constructor) -> Set[int]:
        return self.visit_function(node)


class JavaLoopFinder(JavaLocationsFinder, LoopFinder):
    def visit_loop(self, node) -> Set[int]:
        if node.lineno == self.line:
            lines = set(range(node.lineno, node.end_lineno + 1))
            self.lines |= lines
            return lines
        return self.generic_visit(node)

    def visit_For(self, node: jast.For) -> Set[int]:
        return self.visit_loop(node)

    def visit_ForEach(self, node: jast.ForEach) -> Set[int]:
        return self.visit_loop(node)

    def visit_While(self, node: jast.While) -> Set[int]:
        return self.visit_loop(node)

    def visit_DoWhile(self, node: jast.DoWhile) -> Set[int]:
        return self.visit_loop(node)


class JavaBranchFinder(BranchFinder, JavaLocationsFinder):
    def visit_If(self, node: jast.If) -> Set[int]:
        if node.lineno == self.line:
            start = node.lineno
            end = node.test.end_lineno if node.test is not None else node.lineno
            lines = set(range(start, end + 1))
            if self.then:
                start = node.lineno
                end = node.body.end_lineno
            else:
                if node.orelse is not None:
                    start = node.orelse.lineno
                    end = node.orelse.end_lineno
            lines |= set(range(start, end + 1))
            self.lines |= lines
            return lines
        return self.generic_visit(node)
