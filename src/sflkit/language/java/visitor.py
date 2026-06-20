import jast

from sflkit.language.meta import Injection
from sflkit.language.visitor import ASTVisitor


class JavaInstrumentation(jast.JNodeTransformer, ASTVisitor):
    def parse(self, source: str):
        return jast.parse(source)

    def start_visit(self, ast):
        result = self.visit(ast)
        if isinstance(result, jast.CompilationUnit):
            jlib_import = jast.Import(
                name=jast.qname(
                    [
                        jast.identifier("de"),
                        jast.identifier("cispa"),
                        jast.identifier("sflkitlib"),
                        jast.identifier("JLib"),
                    ]
                )
            )
            result.imports = [jlib_import] + (result.imports or [])
        return result

    def unparse(self, ast):
        return jast.unparse(ast)

    @staticmethod
    def __stmt_list(node: jast.JAST):
        """Return the mutable statement list of ``node.body``.

        jast models method/if/loop bodies as ``Block`` nodes (with an inner
        ``.body`` list), while class bodies are plain lists.  Normalize all of
        these to a mutable list so that injections can be prepended/appended.
        """
        body = node.body
        if isinstance(body, list):
            return body
        if isinstance(body, jast.Block):
            return body.body
        node.body = jast.Block(body=[] if body is None else [body])
        return node.body.body

    @staticmethod
    def __prepend_orelse(node: jast.JAST, stmts):
        orelse = node.orelse
        if orelse is None:
            node.orelse = jast.Block(body=list(stmts))
        elif isinstance(orelse, jast.Block):
            orelse.body[:0] = stmts
        elif isinstance(orelse, list):
            node.orelse = list(stmts) + orelse
        else:
            # e.g. an ``else if`` chain where orelse is an If statement.
            node.orelse = jast.Block(body=list(stmts) + [orelse])

    @staticmethod
    def __is_explicit_constructor_call(stmt):
        # `super(...)` / `this(...)` as a statement; must stay first in a ctor.
        return (
            isinstance(stmt, jast.Expr)
            and isinstance(stmt.value, jast.Call)
            and isinstance(stmt.value.func, (jast.Super, jast.This))
        )

    def __create_node(self, injection: Injection, node: jast.JAST, body=False, body_offset=0):
        if injection.body:
            self.__stmt_list(node)[body_offset:body_offset] = injection.body
        if injection.body_last:
            self.__stmt_list(node).extend(injection.body_last)
        if injection.orelse:
            self.__prepend_orelse(node, injection.orelse)
        if injection.assign:
            if hasattr(node, "value"):
                node.value = injection.assign
            elif hasattr(node, "test"):
                node.test = injection.assign
        if injection.finalbody:
            if hasattr(node, "final"):
                node.final = injection.finalbody + node.final
            else:
                if body:
                    node.body = jast.Block(
                        body=[
                            jast.Try(
                                body=node.body
                                if isinstance(node.body, jast.Block)
                                else jast.Block(body=self.__stmt_list(node)),
                                final=jast.Block(body=injection.finalbody),
                            )
                        ]
                    )
                else:
                    node = jast.Try(
                        body=jast.Block(body=[node]),
                        final=jast.Block(body=injection.finalbody),
                    )
        if injection.error:
            error_var = jast.identifier(self.meta_visitor.tmp_generator.get_var_name())
            raise_stmt = [
                jast.Throw(
                    exc=jast.Name(id=error_var),
                )
            ]
            if body:
                inner = (
                    node.body
                    if isinstance(node.body, jast.Block)
                    else jast.Block(body=self.__stmt_list(node))
                )
            else:
                inner = jast.Block(body=[node])
            node = jast.Try(
                body=inner,
                catches=[
                    jast.catch(
                        excs=[jast.qname([jast.identifier("Exception")])],
                        id=error_var,
                        body=jast.Block(body=injection.error + raise_stmt),
                    )
                ],
            )
        if injection.pre or injection.post:
            return jast.Compound(
                body=injection.pre + [node] + injection.post,
            )
        decls = [node]
        if injection.pre_block:
            decls = [
                jast.Initializer(body=jast.Block(body=injection.pre_block))
            ] + decls
        if injection.post_block:
            decls = decls + [
                jast.Initializer(body=jast.Block(body=injection.post_block))
            ]
        if injection.static_pre_block:
            decls = [
                jast.Initializer(
                    body=jast.Block(body=injection.static_pre_block), static=True
                )
            ] + decls
        if injection.static_post_block:
            decls = decls + [
                jast.Initializer(
                    body=jast.Block(body=injection.static_post_block), static=True
                )
            ]
        if len(decls) == 1:
            return decls[0]
        return jast.CompoundDecl(body=decls)

    def visit_Block(self, node: jast.Block) -> jast.JAST:
        # Recurse into the block's statements but do not instrument the block
        # itself (Java has no statement-list bodies; a Block is a grouping node).
        node.body = [self.visit(n) for n in node.body]
        return node

    def __visit_function(self, node) -> jast.JAST:
        if node.body is None:
            return node
        self.meta_visitor.enter_function(node)
        injection = self.meta_visitor.visit_start(node)
        stmts = self.__stmt_list(node)
        # An explicit super()/this() call must remain the first statement of a
        # constructor, so keep it uninstrumented and inject everything after it.
        leading = stmts[:1] if stmts and self.__is_explicit_constructor_call(stmts[0]) else []
        rest = stmts[len(leading):]
        stmts[:] = leading + [self.visit(n) for n in list(rest)]
        self.meta_visitor.exit_function(node)
        self.events += injection.events
        return self.__create_node(
            injection, node, body=True, body_offset=len(leading)
        )

    def visit_Method(self, node: jast.Method) -> jast.JAST:
        return self.__visit_function(node)

    def visit_Constructor(self, node: jast.Constructor) -> jast.JAST:
        return self.__visit_function(node)

    def __visit_class(self, node):
        self.meta_visitor.enter_class(node)
        injection = self.meta_visitor.visit_start(node)
        node.body = [self.visit(n) for n in node.body]
        self.meta_visitor.exit_class(node)
        self.events += injection.events
        return self.__create_node(injection, node)

    def visit_Class(self, node: jast.Class) -> jast.JAST:
        return self.__visit_class(node)

    def visit_Enum(self, node: jast.Enum) -> jast.JAST:
        return self.__visit_class(node)

    def visit_Record(self, node: jast.Record) -> jast.JAST:
        return self.__visit_class(node)

    def visit_Interface(self, node: jast.Interface) -> jast.JAST:
        return self.__visit_class(node)

    def visit_AnnotationDecl(self, node: jast.AnnotationDecl) -> jast.JAST:
        return self.__visit_class(node)

    def __visit_control(self, node) -> jast.JAST:
        # Control-flow statements: the event factories derive their events from
        # the condition/init/update clauses, so we must NOT recurse into those
        # (an expression position cannot hold a wrapping Compound).  We only
        # recurse into the statement bodies, normalizing brace-less bodies to
        # Blocks so injected events stay scoped to the branch.
        injection = self.meta_visitor.visit_start(node)
        self.events += injection.events
        body = getattr(node, "body", None)
        if isinstance(body, jast.Block):
            node.body = self.visit(body)
        elif isinstance(body, jast.JAST):
            node.body = jast.Block(body=[self.visit(body)])
        orelse = getattr(node, "orelse", None)
        if orelse is not None:
            if isinstance(orelse, jast.Block):
                node.orelse = self.visit(orelse)
            else:
                node.orelse = jast.Block(body=[self.visit(orelse)])
        return self.__create_node(injection, node)

    def visit_If(self, node: jast.If) -> jast.JAST:
        return self.__visit_control(node)

    @staticmethod
    def __for_clause_stmts(clause):
        """Normalize a for-loop init/update clause to a list of statements."""
        if clause is None:
            return []
        items = clause if isinstance(clause, list) else [clause]
        stmts = []
        for item in items:
            if isinstance(item, jast.stmt):
                stmts.append(item)
            else:
                expr = jast.Expr(value=item)
                expr.lineno = getattr(item, "lineno", None)
                expr.end_lineno = getattr(item, "end_lineno", expr.lineno)
                stmts.append(expr)
        return stmts

    def visit_For(self, node: jast.For) -> jast.JAST:
        # Desugar ``for (init; test; update) body`` into
        # ``{ init; while (test) { body; update; } }`` so that variables declared
        # in the for-init are in scope for every injected event (jast scopes them
        # to the loop) and for-loops reuse the while-loop instrumentation path.
        # NOTE: ``update`` runs at the end of the body, which differs from ``for``
        # only under ``continue`` (a documented limitation).
        init_stmts = self.__for_clause_stmts(node.init)
        update_stmts = self.__for_clause_stmts(node.update)
        if isinstance(node.body, jast.Block):
            body_stmts = list(node.body.body)
        elif node.body is not None:
            body_stmts = [node.body]
        else:
            body_stmts = []
        if node.test is not None:
            test = node.test
        else:
            test = jast.Constant(jast.BoolLiteral(True))
            test.lineno = node.lineno
            test.end_lineno = node.end_lineno
        while_node = jast.While(
            test=test, body=jast.Block(body=body_stmts + update_stmts)
        )
        while_node.lineno = node.lineno
        while_node.end_lineno = node.end_lineno
        block = jast.Block(body=init_stmts + [while_node])
        block.lineno = node.lineno
        block.end_lineno = node.end_lineno
        return self.visit(block)

    def visit_ForEach(self, node: jast.ForEach) -> jast.JAST:
        return self.__visit_control(node)

    def visit_While(self, node: jast.While) -> jast.JAST:
        return self.__visit_control(node)

    def visit_DoWhile(self, node: jast.DoWhile) -> jast.JAST:
        return self.__visit_control(node)

    def generic_visit(self, node: jast.JAST) -> jast.JAST:
        injection = self.meta_visitor.visit_start(node)
        self.events += injection.events
        # Recurse only into statement/declaration positions, never into
        # expressions: every value/condition/use event is produced by the
        # factories at the statement level, and an expression slot cannot hold
        # a wrapping Compound statement.
        for field, value in list(node):
            if isinstance(value, list):
                setattr(
                    node,
                    field,
                    [
                        self.visit(item)
                        if isinstance(item, jast.JAST)
                        and not isinstance(item, jast.expr)
                        else item
                        for item in value
                    ],
                )
            elif isinstance(value, jast.JAST) and not isinstance(value, jast.expr):
                setattr(node, field, self.visit(value))
        return self.__create_node(injection, node)
