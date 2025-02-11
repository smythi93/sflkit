import jast

from sflkit.language.meta import Injection
from sflkit.language.visitor import ASTVisitor


class JavaInstrumentation(jast.JNodeTransformer, ASTVisitor):
    def parse(self, source: str):
        return jast.parse(source)

    def start_visit(self, ast):
        return self.visit(ast)

    def unparse(self, ast):
        return jast.unparse(ast)

    def __create_node(self, injection: Injection, node: jast.JAST, body=False):
        if injection.body:
            node.body = injection.body + node.body
        if injection.body_last:
            node.body += injection.body_last
        if injection.orelse:
            node.orelse = injection.orelse + node.orelse
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
                    node.body = [
                        jast.Try(
                            body=node.body,
                            final=injection.finalbody,
                        )
                    ]
                else:
                    node = jast.Try(
                        body=[node],
                        final=injection.finalbody,
                    )
        if injection.error:
            error_var = jast.identifier(self.meta_visitor.tmp_generator.get_var_name())
            raise_stmt = [
                jast.Throw(
                    exc=jast.Name(id=error_var),
                )
            ]
            if body:
                body = node.body
                if isinstance(body, list):
                    body = jast.Block(body)
            else:
                body = jast.Block([node])
            node = jast.Try(
                body=body,
                catches=[
                    jast.catch(
                        excs=[
                            jast.qname(
                                [
                                    jast.identifier(
                                        "Exception",
                                    )
                                ],
                                id=error_var,
                                body=jast.Block(
                                    body=injection.error + raise_stmt,
                                ),
                            )
                        ],
                    )
                ],
            )
        if injection.pre or injection.post:
            return jast.Compound(
                body=injection.pre + [node] + injection.post,
            )
        body = [node]
        if injection.pre_block:
            node = [
                jast.Initializer(
                    block=jast.Block(
                        body=injection.pre_block,
                    ),
                )
            ] + body
        if injection.post_block:
            body += [
                jast.Initializer(
                    block=jast.Block(
                        body=injection.post_block,
                    ),
                )
            ]
        if injection.static_pre_block:
            node = [
                jast.Initializer(
                    block=jast.Block(
                        body=injection.static_pre_block,
                    ),
                    static=True,
                )
            ] + node
        if injection.static_post_block:
            body += [
                jast.Initializer(
                    block=jast.Block(
                        body=injection.static_post_block,
                    ),
                    static=True,
                )
            ]
        if len(body) == 1:
            return body[0]
        return jast.CompoundDecl(
            body=body,
        )

    def __visit_function(self, node: jast.Method | jast.Constructor) -> jast.JAST:
        self.meta_visitor.enter_function(node)
        injection = self.meta_visitor.visit_start(node)
        node.body = [self.visit(n) for n in node.body]
        self.meta_visitor.exit_function(node)
        self.events += injection.events
        return self.__create_node(injection, node, body=True)

    def visit_Method(self, node: jast.Method) -> jast.JAST:
        return self.__visit_function(node)

    def visit_Constructor(self, node: jast.Constructor) -> jast.JAST:
        return self.__visit_function(node)

    def __visit_class(
        self,
        node: jast.Class
        | jast.Enum
        | jast.Record
        | jast.Interface
        | jast.AnnotationDecl,
    ):
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

    def generic_visit(self, node: jast.JAST) -> jast.JAST:
        injection = self.meta_visitor.visit_start(node)
        self.events += injection.events
        super().generic_visit(node)
        return self.__create_node(injection, node)
