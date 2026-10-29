import abc
from typing import List, Dict

import jast

from sflkit.language.java.extract import ReturnFinder
from sflkit.language.meta import MetaVisitor, IDGenerator, TmpGenerator, Injection
from sflkitlib.events.event import (
    Event,
    LineEvent,
    BranchEvent,
    DefEvent,
    FunctionEnterEvent,
    FunctionExitEvent,
    FunctionErrorEvent,
    LoopBeginEvent,
    LoopHitEvent,
    LoopEndEvent,
    UseEvent,
    ConditionEvent,
    LenEvent,
    TestStartEvent,
    TestEndEvent,
    TestLineEvent,
    TestDefEvent,
    TestUseEvent,
    TestAssertEvent,
)

java_lib_name = jast.identifier("JLib")


def get_call(function: jast.identifier, *args) -> jast.Expr:
    return jast.Expr(
        value=jast.Member(
            value=jast.Name(id=java_lib_name),
            member=jast.Call(
                func=jast.Name(id=function),
                args=list(args),
            ),
        )
    )


def java_lib_get_id(*args) -> jast.expr:
    return get_call(jast.identifier("getID"), *args).value


def java_lib_get_type(*args) -> jast.expr:
    return get_call(jast.identifier("getType"), *args).value


def java_lib_get_len(*args) -> jast.expr:
    return get_call(jast.identifier("getLen"), *args).value


def java_lib_has_len(*args) -> jast.expr:
    return get_call(jast.identifier("hasLen"), *args).value


class JavaEventFactory(MetaVisitor, jast.JNodeVisitor, abc.ABC):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language, event_id_generator, function_id_generator, tmp_generator
        )
        # Stack of booleans: whether each enclosing class is a context in which
        # static members (in particular static initializer blocks) may be
        # declared.  A non-static member ("inner") class is not, so field
        # instrumentation must avoid emitting static blocks there.
        self._class_static_ctx = []
        # Stack of the enclosing class nodes, to query the innermost kind.
        self._class_stack = []

    def enter_class(self, class_):
        parent_static = self._class_static_ctx[-1] if self._class_static_ctx else True
        is_top_level = not self._class_static_ctx
        implicitly_static = isinstance(
            class_, (jast.Interface, jast.Enum, jast.Record, jast.AnnotationDecl)
        )
        declared_static = any(
            isinstance(mod, jast.Static) for mod in (getattr(class_, "modifiers", None) or [])
        )
        self._class_static_ctx.append(
            is_top_level or implicitly_static or (declared_static and parent_static)
        )
        self._class_stack.append(class_)

    def exit_class(self, class_):
        if self._class_static_ctx:
            self._class_static_ctx.pop()
        if self._class_stack:
            self._class_stack.pop()

    def _can_declare_static(self) -> bool:
        return self._class_static_ctx[-1] if self._class_static_ctx else True

    def _in_interface(self) -> bool:
        # Interfaces and annotation types allow no initializer blocks at all
        # (their fields are implicit constants), so fields there cannot be
        # instrumented with the pre/post/static blocks the factories emit.
        return bool(self._class_stack) and isinstance(
            self._class_stack[-1], (jast.Interface, jast.AnnotationDecl)
        )

    @staticmethod
    def _can_complete_normally(stmt) -> bool:
        # Conservative Java reachability check: can control fall through past
        # ``stmt``?  Used to avoid placing an event after a body that always
        # throws/returns/breaks (which would be an unreachable statement).
        # Defaults to True for anything not recognized.
        if stmt is None:
            return True
        if isinstance(stmt, (jast.Throw, jast.Return, jast.Break, jast.Continue)):
            return False
        if isinstance(stmt, (jast.Block, jast.Compound)):
            body = stmt.body if isinstance(stmt.body, list) else [stmt.body]
            return not body or JavaEventFactory._can_complete_normally(body[-1])
        if isinstance(stmt, jast.If):
            if stmt.orelse is None:
                return True
            return JavaEventFactory._can_complete_normally(
                stmt.body
            ) or JavaEventFactory._can_complete_normally(stmt.orelse)
        return True

    @classmethod
    def _body_completes(cls, node) -> bool:
        body = node.body
        stmts = (
            body.body
            if isinstance(body, jast.Block)
            else body
            if isinstance(body, list)
            else [body]
        )
        return not stmts or cls._can_complete_normally(stmts[-1])

    def visit_start(self, *args) -> Injection:
        # A visit_* method may fall through and return None (e.g. an assignment
        # whose target is not a simple variable); treat that as no injection.
        return self.visit(*args) or Injection()

    def generic_visit(self, node):
        return Injection()

    def default_result(self):
        return Injection()

    @abc.abstractmethod
    def get_function(self) -> jast.identifier:
        pass

    def get_event_call(self, event: Event):
        return get_call(
            self.get_function(), jast.Constant(jast.IntLiteral(event.event_id))
        )


class LineEventFactory(JavaEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addLineEvent")

    def get_event(self, node: jast.stmt):
        return LineEvent(self.file, node.lineno, self.event_id_generator.get_next_id())

    def visit_line(self, node: jast.stmt) -> Injection:
        line_event = self.get_event(node)
        return Injection(pre=[self.get_event_call(line_event)], events=[line_event])

    def generic_visit(self, node):
        if isinstance(node, jast.stmt):
            return self.visit_line(node)
        return super().generic_visit(node)

    def visit_Field(self, node):
        if self._in_interface():
            return Injection()
        line_event = LineEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id()
        )
        is_static = any(isinstance(mod, jast.Static) for mod in node.modifiers)
        if is_static:
            if not self._can_declare_static():
                # static field in a non-static inner class: a static initializer
                # block would be an illegal static declaration, so skip it.
                return Injection()
            return Injection(
                static_pre_block=[self.get_event_call(line_event)], events=[line_event]
            )
        return Injection(
            pre_block=[self.get_event_call(line_event)], events=[line_event]
        )


class BranchEventFactory(JavaEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language, event_id_generator, function_id_generator, tmp_generator, **kwargs
        )
        self.branch_id = 0

    def get_function(self) -> jast.identifier:
        return jast.identifier("addBranchEvent")

    def _get_branch_events(self, node: jast.stmt):
        then_branch_event = BranchEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.branch_id,
            self.branch_id + 1,
        )
        else_branch_event = BranchEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.branch_id + 1,
            self.branch_id,
        )
        self.branch_id += 2
        return then_branch_event, else_branch_event

    def visit_If(self, node: jast.If):
        then_branch_event, else_branch_event = self._get_branch_events(node)
        return Injection(
            body=[self.get_event_call(then_branch_event)],
            orelse=[self.get_event_call(else_branch_event)],
            events=[then_branch_event, else_branch_event],
        )

    @staticmethod
    def _never_falls_through(node) -> bool:
        # A loop a false condition can never exit: `while (true)`,
        # `do {} while (true)`, `for (;;)` / `for (; true;)`.  Java treats the
        # code after it as unreachable, so the exit-branch event must not be
        # placed there.
        test = getattr(node, "test", None)
        if test is None:
            return isinstance(node, jast.For)
        return (
            isinstance(test, jast.Constant)
            and isinstance(test.value, jast.BoolLiteral)
            and bool(test.value)
        )

    def _visit_loop(self, node: jast.For | jast.ForEach | jast.While | jast.DoWhile):
        then_branch_event, else_branch_event = self._get_branch_events(node)
        # Keep both branch ids registered (no gaps in the mapping), but do not
        # emit the exit-branch call after a non-terminating loop; it would be
        # unreachable and the branch is simply never taken.
        post = (
            []
            if self._never_falls_through(node)
            else [self.get_event_call(else_branch_event)]
        )
        return Injection(
            body=[self.get_event_call(then_branch_event)],
            post=post,
            events=[then_branch_event, else_branch_event],
        )

    def visit_For(self, node: jast.For):
        return self._visit_loop(node)

    def visit_ForEach(self, node: jast.ForEach):
        return self._visit_loop(node)

    def visit_While(self, node: jast.While):
        return self._visit_loop(node)

    def visit_DoWhile(self, node: jast.DoWhile):
        return self._visit_loop(node)

    def _visit_single_branch(self, node: jast.stmt):
        branch_event = BranchEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.branch_id,
            -1,
        )
        return Injection(
            body=[self.get_event_call(branch_event)],
            events=[branch_event],
        )

    def visit_catch(self, node: jast.catch):
        return self._visit_single_branch(node)

    def visit_switchgroup(self, node: jast.switchgroup):
        return self._visit_single_branch(node)

    def visit_switchexprule(self, node: jast.switchexprule):
        return self._visit_single_branch(node)


class DefEventFactory(JavaEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addDefEvent")

    def get_event(self, node: jast.stmt | jast.declaration, var: str):
        return DefEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), var
        )

    def get_event_call(self, event: DefEvent):
        call = super().get_event_call(event)
        assert isinstance(call.value, jast.Member)
        assert isinstance(call.value.member, jast.Call)
        call.value.member.args.append(java_lib_get_id(jast.Name(id=event.var)))
        call.value.member.args.append(jast.Name(id=event.var))
        return call

    def visit_Method(self, node: jast.Method):
        def_events = []
        for param in node.parameters.parameters:
            def_events.append(self.get_event(node, param.id.id.value))
        return Injection(
            body=[self.get_event_call(event) for event in def_events],
            events=def_events,
        )

    def visit_Constructor(self, node: jast.Constructor):
        def_events = []
        if node.parameters:
            for param in node.parameters.parameters:
                def_events.append(self.get_event(node, param.id.id.value))
        return Injection(
            body=[self.get_event_call(event) for event in def_events],
            events=def_events,
        )

    def visit_LocalVariable(self, node: jast.LocalVariable):
        # only declarators with an initializer define a value; an uninitialized
        # local (e.g. `int i;`) must not be read by a def event before assignment
        def_events = [
            self.get_event(node, var.id.id.value)
            for var in node.declarators
            if var.init is not None
        ]
        if not def_events:
            return Injection()
        return Injection(
            post=[self.get_event_call(event) for event in def_events],
            events=def_events,
        )

    def visit_Field(self, node: jast.Field):
        if self._in_interface():
            return Injection()
        # Only fields with an initializer define a value at their declaration.
        # An uninitialized field (often final, assigned in a constructor) must
        # not be read by an initializer block before it is assigned.
        def_events = [
            self.get_event(node, var.id.id.value)
            for var in node.declarators
            if var.init is not None
        ]
        if not def_events:
            return Injection()
        is_static = any(isinstance(mod, jast.Static) for mod in node.modifiers)
        if is_static:
            if not self._can_declare_static():
                return Injection()
            return Injection(
                static_post_block=[self.get_event_call(event) for event in def_events],
                events=def_events,
            )
        return Injection(
            post_block=[self.get_event_call(event) for event in def_events],
            events=def_events,
        )

    def visit_For(self, node: jast.For):
        # the loop is not desugared, so record the for-init definition inside the
        # loop body where the variable is in scope (not after the loop)
        if node.init:
            if isinstance(node.init, jast.LocalVariable):
                injection = self.visit_LocalVariable(node.init)
            else:
                injection = Injection()
                for var in node.init:
                    injection += self.visit(var)
            return Injection(body=injection.post, events=injection.events)
        return Injection()

    def visit_ForEach(self, node: jast.ForEach):
        def_event = self.get_event(node, node.id.id.value)
        return Injection(
            body=[self.get_event_call(def_event)],
            events=[def_event],
        )

    def visit_Expr(self, node):
        if isinstance(node.value, jast.Assign):
            return self.visit(node.value)
        return Injection()

    def visit_Assign(self, node: jast.Assign):
        var = self.variable_extract.visit(node.target)
        if var and len(var) == 1:
            def_event = self.get_event(node, list(var)[0])
            return Injection(
                post=[self.get_event_call(def_event)],
                events=[def_event],
            )

    def visit_TryWithResources(self, node: jast.TryWithResources):
        def_events = []
        for resource in node.resources:
            if isinstance(resource, jast.resource):
                def_events.append(self.get_event(node, resource.variable.id.id.value))
        return Injection(
            body=[self.get_event_call(event) for event in def_events],
            events=def_events,
        )

    def visit_Catch(self, node: jast.catch):
        def_event = self.get_event(node, node.id.value)
        return Injection(
            body=[self.get_event_call(def_event)],
            events=[def_event],
        )


class FunctionEventFactory(JavaEventFactory):
    # node -> logical function id; shared across the enter/exit/error factories
    # (via the shared function_id_generator) so they agree on a function's id.
    functions: Dict[jast.Method, int] = dict()
    return_visitor: ReturnFinder = ReturnFinder()

    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language, event_id_generator, function_id_generator, tmp_generator, **kwargs
        )
        self.function_stack: List[jast.Method] = list()
        # per-factory (instance) so that, e.g., the exit and the error factory do
        # NOT share event ids for the same function, and so state does not leak
        # across instrumentation runs.
        self.functions_exit_id: Dict[jast.Method, int] = dict()
        self.function_var: Dict[jast.Method, jast.identifier] = dict()

    def get_function_id(self, node: jast.Method):
        if node in self.functions:
            return self.functions[node]
        self.functions[node] = self.function_id_generator.get_next_id()
        return self.functions[node]

    def get_function_event_id(self, node: jast.Method):
        if node in self.functions_exit_id:
            return self.functions_exit_id[node]
        self.functions_exit_id[node] = self.event_id_generator.get_next_id()
        return self.functions_exit_id[node]

    def get_function_var(self, node: jast.Method):
        if node in self.function_var:
            return self.function_var[node]
        self.function_var[node] = jast.identifier(self.tmp_generator.get_var_name())
        return self.function_var[node]

    def enter_function(self, function: jast.Method):
        self.function_stack.append(function)

    def exit_function(self, function: jast.Method):
        self.function_stack.pop()


class FunctionEnterEventFactory(FunctionEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addFunctionEnterEvent")

    def visit_Method(self, node: jast.Method):
        function_enter_event = FunctionEnterEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            node.id.value,
            self.get_function_id(node),
        )
        return Injection(
            body=[self.get_event_call(function_enter_event)],
            events=[function_enter_event],
        )


class FunctionExitEventFactory(FunctionEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addFunctionExitEvent")

    def get_event_call(self, event: FunctionExitEvent):
        call = super().get_event_call(event)
        assert isinstance(call.value, jast.Member)
        assert isinstance(call.value.member, jast.Call)
        # JLib.addFunctionExitEvent(eventID, returnValue); the type is derived
        # from the value by JLib.  void methods report a null return value.
        if event.tmp_var is not None:
            call.value.member.args.append(jast.Name(id=event.tmp_var))
        else:
            call.value.member.args.append(jast.Constant(jast.NullLiteral()))
        return call

    @staticmethod
    def _is_void(return_type) -> bool:
        return return_type is None or isinstance(return_type, jast.Void)

    def visit_Method(self, node: jast.Method):
        if self._is_void(node.return_type):
            # void method: no return value to capture; only record exit on
            # fall-through (explicit `return;` are handled by visit_Return).  A
            # body that always throws/returns has no reachable fall-through.
            if self.return_visitor.visit(node) or not self._body_completes(node):
                return Injection()
            function_exit_event = FunctionExitEvent(
                self.file,
                node.lineno,
                self.get_function_event_id(node),
                node.id.value,
                self.get_function_id(node),
                tmp_var=None,
            )
            return Injection(
                body_last=[self.get_event_call(function_exit_event)],
                events=[function_exit_event],
            )
        function_var = self.get_function_var(node)
        if isinstance(node.return_type, jast.Boolean):
            value = jast.Constant(jast.BoolLiteral(False))
        elif isinstance(node.return_type, jast.primitivetype):
            value = jast.Constant(jast.IntLiteral(0))
        else:
            value = jast.Constant(jast.NullLiteral())
        if not self.return_visitor.visit(node) and self._body_completes(node):
            function_exit_event = FunctionExitEvent(
                self.file,
                node.lineno,
                self.get_function_event_id(node),
                node.id.value,
                self.get_function_id(node),
                tmp_var=function_var,
            )
            body_last = [self.get_event_call(function_exit_event)]
            events = [function_exit_event]
        else:
            body_last = []
            events = []
        return Injection(
            body=[
                jast.LocalVariable(
                    type=node.return_type,
                    declarators=[
                        jast.declarator(
                            id=jast.variabledeclaratorid(id=function_var),
                            init=value,
                        )
                    ],
                )
            ],
            body_last=body_last,
            events=events,
        )

    def visit_Return(self, node):
        function = self.function_stack[-1]
        if node.value is None:
            # void `return;`: record the exit, leave the statement unchanged
            function_exit_event = FunctionExitEvent(
                self.file,
                node.lineno,
                self.get_function_event_id(node),
                function.id.value,
                self.get_function_id(function),
                tmp_var=None,
            )
            return Injection(
                pre=[self.get_event_call(function_exit_event)],
                events=[function_exit_event],
            )
        function_var = self.get_function_var(function)
        function_exit_event = FunctionExitEvent(
            self.file,
            node.lineno,
            self.get_function_event_id(node),
            function.id.value,
            self.get_function_id(function),
            tmp_var=function_var,
        )
        return Injection(
            pre=[
                jast.Expr(
                    value=jast.Assign(
                        target=jast.Name(id=function_var),
                        value=node.value,
                    )
                ),
                self.get_event_call(function_exit_event),
            ],
            assign=jast.Name(id=function_var),
            events=[function_exit_event],
        )


class FunctionErrorEventFactory(FunctionEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addFunctionErrorEvent")

    def visit_Method(self, node: jast.Method):
        function_error_event = FunctionErrorEvent(
            self.file,
            node.lineno,
            self.get_function_event_id(node),
            node.id.value,
            self.get_function_id(node),
        )
        return Injection(
            error=[self.get_event_call(function_error_event)],
            events=[function_error_event],
        )


class LoopEventFactory(JavaEventFactory):
    loops: Dict[jast.stmt, int] = dict()
    loop_id: int = 0

    def get_loop_id(self, node: jast.stmt):
        if node in self.loops:
            return self.loops[node]
        self.loops[node] = self.loop_id
        self.loop_id += 1
        return self.loops[node]

    def visit_loop(self, node: jast.For | jast.ForEach | jast.While | jast.DoWhile):
        pass

    def visit_For(self, node: jast.For):
        return self.visit_loop(node)

    def visit_ForEach(self, node: jast.ForEach):
        return self.visit_loop(node)

    def visit_While(self, node: jast.While):
        return self.visit_loop(node)

    def visit_DoWhile(self, node: jast.DoWhile):
        return self.visit_loop(node)


class LoopBeginEventFactory(LoopEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addLoopBeginEvent")

    def visit_loop(self, node: jast.For | jast.ForEach | jast.While | jast.DoWhile):
        loop_begin_event = LoopBeginEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.get_loop_id(node),
        )
        return Injection(
            pre=[self.get_event_call(loop_begin_event)],
            events=[loop_begin_event],
        )


class LoopHitEventFactory(LoopEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addLoopHitEvent")

    def visit_loop(self, node: jast.For | jast.ForEach | jast.While | jast.DoWhile):
        loop_hit_event = LoopHitEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.get_loop_id(node),
        )
        return Injection(
            body=[self.get_event_call(loop_hit_event)],
            events=[loop_hit_event],
        )


class LoopEndEventFactory(LoopEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addLoopEndEvent")

    def visit_loop(self, node: jast.For | jast.ForEach | jast.While | jast.DoWhile):
        loop_end_event = LoopEndEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.get_loop_id(node),
        )
        return Injection(
            finalbody=[self.get_event_call(loop_end_event)],
            events=[loop_end_event],
        )


class UseEventFactory(JavaEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addUseEvent")

    def get_event_call(self, event: UseEvent):
        call = super().get_event_call(event)
        assert isinstance(call.value, jast.Member)
        assert isinstance(call.value.member, jast.Call)
        call.value.member.args.append(java_lib_get_id(jast.Name(id=event.var)))
        return call

    def get_event(self, node: jast.stmt | jast.declaration, var: str):
        return UseEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), var
        )

    @staticmethod
    def _embedded_assign_targets(node) -> set:
        # Names assigned by an assignment nested inside an expression, e.g. `f`
        # in `x = (f = g()) != null ? f : h()`.  Such a variable is not assigned
        # before the statement, so a use of it must not be hoisted to `pre`.  We
        # skip a statement-level assignment's own target (it is harmless, like
        # the read in `x = x + 1`) and only scan the value side.
        expr = node.value if isinstance(node, jast.Expr) else node
        value = expr.value if isinstance(expr, jast.Assign) else expr
        targets = set()
        stack = [value]
        while stack:
            current = stack.pop()
            if isinstance(current, jast.Assign):
                if isinstance(current.target, jast.Name):
                    targets.add(str(current.target.id))
                stack.append(current.value)
                continue
            if isinstance(current, jast.JAST):
                for _, child in current:
                    if isinstance(child, list):
                        stack.extend(c for c in child if isinstance(c, jast.JAST))
                    elif isinstance(child, jast.JAST):
                        stack.append(child)
        return targets

    def visit_use(self, node: jast.stmt | jast.declaration):
        uses = self.use_extract.visit(node)
        embedded = self._embedded_assign_targets(node)
        use_events = [
            self.get_event(node, use)
            for use in uses
            if use.split(".")[0] not in embedded
        ]
        return Injection(
            pre=[self.get_event_call(event) for event in use_events],
            events=use_events,
        )

    def visit_Field(self, node):
        if self._in_interface():
            return Injection()
        injection = self.visit_use(node)
        is_static = any(isinstance(mod, jast.Static) for mod in node.modifiers)
        if is_static:
            if not self._can_declare_static():
                return Injection()
            return Injection(
                static_pre_block=injection.pre,
                events=injection.events,
            )
        return Injection(
            pre_block=injection.pre,
            events=injection.events,
        )

    def _use_test(self, test):
        # A test that assigns a variable (e.g. `(ch = str.charAt(i)) < 0x20`)
        # cannot have its uses hoisted to before the statement: the assigned
        # variable is not yet definitely assigned there.  Skip it, mirroring the
        # condition factory's handling of such tests.
        if test is None or self.condition_extract.contains_assign(test):
            return Injection()
        return self.visit_use(test)

    def visit_If(self, node: jast.If):
        return self._use_test(node.test)

    def visit_Switch(self, node: jast.Switch):
        return self._use_test(node.value)

    @staticmethod
    def _declared_names(node) -> set:
        if isinstance(node, jast.LocalVariable):
            return {str(declarator.id.id) for declarator in node.declarators}
        return set()

    @staticmethod
    def _uninitialized_names(node) -> set:
        # for-init variables declared without an initializer (e.g. `charCount`
        # in `for (int charCount, i = 0; ...)`), which are not assigned at the
        # start of the body.
        if isinstance(node, jast.LocalVariable):
            return {
                str(declarator.id.id)
                for declarator in node.declarators
                if declarator.init is None
            }
        return set()

    def visit_For(self, node: jast.For):
        injection = Injection()
        declared, uninitialized = set(), set()
        if node.init:
            inits = (
                [node.init] if isinstance(node.init, jast.LocalVariable) else node.init
            )
            for var in inits:
                injection += self.visit_use(var)
                declared |= self._declared_names(var)
                uninitialized |= self._uninitialized_names(var)
        test = Injection()
        if node.test:
            test += self.visit_use(node.test)
        # the loop is not desugared: init uses of *external* variables are in
        # scope before the loop, but a use of a variable declared in the init
        # itself (e.g. `for (int i = 0, end = i + 4; ...)`) is only in scope
        # inside the body, alongside the test/update uses.  We do not append to
        # the body end (body_last) because a body ending in a return/break would
        # make them unreachable, and the native for handles the update itself.
        init_pre, init_body = [], []
        for call, event in zip(injection.pre, injection.events):
            (init_body if event.var.split(".")[0] in declared else init_pre).append(call)
        # The update runs at the body end, so its uses are placed at the body
        # start as an approximation -- but a use of a for-init variable that has
        # no initializer (assigned only in the body, e.g. `i += charCount`) is
        # not yet definitely assigned there, so drop it.
        update_pre, update_events = [], []
        for var in node.update or []:
            update = self.visit_use(var)
            for call, event in zip(update.pre, update.events):
                if event.var.split(".")[0] in uninitialized:
                    continue
                update_pre.append(call)
                update_events.append(event)
        return Injection(
            pre=init_pre,
            body=init_body + test.pre + update_pre,
            events=injection.events + test.events + update_events,
        )

    def visit_ForEach(self, node: jast.ForEach):
        return self.visit_use(node.iter)

    def visit_While(self, node: jast.While):
        # The while-condition variables are in scope before the loop, so record
        # their uses there (once).  We do NOT also append them at the body end:
        # a `continue` would skip that copy, and a body that always
        # throws/returns/continues would make it an unreachable statement.
        # `_use_test` also skips conditions that assign a variable (e.g.
        # `while ((c = next()) != EOF)`), whose use cannot be hoisted before it.
        injection = self._use_test(node.test)
        return Injection(
            pre=injection.pre,
            events=injection.events,
        )

    def visit_DoWhile(self, node: jast.DoWhile):
        # A do-while evaluates its condition after the body, so the uses go at
        # the body end -- but only when the body can fall through there (else
        # they would be unreachable).
        injection = self._use_test(node.test)
        if not self._body_completes(node):
            return Injection(events=injection.events)
        return Injection(
            body_last=injection.pre,
            events=injection.events,
        )

    def visit_TryWithResources(self, node: jast.TryWithResources):
        injection = Injection()
        for resource in node.resources:
            if isinstance(resource, jast.resource):
                injection += self.visit_use(resource.variable)
        return injection

    def visit_Assert(self, node: jast.Assert):
        if node.msg:
            return self.visit_use(node.test) + self.visit_use(node.msg)
        return self.visit_use(node.test)

    def visit_Throw(self, node: jast.Throw):
        return self.visit_use(node.exc)

    def visit_Expr(self, node: jast.Expr):
        return self.visit_use(node.value)

    def visit_Return(self, node):
        if node.value:
            return self.visit_use(node.value)
        return Injection()

    def visit_Yield(self, node: jast.Yield):
        return self.visit_use(node.value)

    def visit_Synch(self, node: jast.Synch):
        return self.visit_use(node.lock)


class ConditionEventFactory(JavaEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addConditionEvent")

    def get_event_call(self, event: ConditionEvent):
        call = super().get_event_call(event)
        assert isinstance(call.value, jast.Member)
        assert isinstance(call.value.member, jast.Call)
        call.value.member.args.append(jast.Name(id=event.tmp_var))
        return call

    def visit_condition(self, node: jast.If | jast.While | jast.DoWhile | jast.For):
        # A test that assigns a later-used variable (e.g.
        # `cs == null || (strLen = cs.length()) == 0`) cannot be hoisted into a
        # tmp: the intermediate boolean hides the assignment from Java's
        # definite-assignment analysis, so a later use of the variable fails to
        # compile.  Leave such tests in place (no condition event recorded).
        if node.test and not self.condition_extract.contains_assign(node.test):
            self.condition_extract.setup(self)
            var, var_use, var_assign, events = self.condition_extract.visit(node.test)
            return Injection(
                pre=[var_assign],
                assign=var_use,
                events=events,
            )
        return Injection()

    def _inline_condition(self, node):
        """Record a loop condition inline.

        Replaces ``cond`` with ``JLib.evalCondition(id, (cond))``, which logs the
        condition event and returns the value.  Unlike hoisting the condition
        into the loop body, this fires on every check (including after a
        ``continue``), keeps the test in scope (the for-loop variable), and never
        produces unreachable or definitely-unassigned code.  It records only the
        loop's overall condition value, not decomposed ``&&``/``||`` operands.
        """
        if node.test is None:
            return Injection()
        # A constant boolean condition matters to Java's reachability analysis:
        # `while (true)` makes the code after the loop unreachable, so the
        # enclosing method needs no trailing return.  Wrapping it in a call
        # hides the constant and breaks that analysis, so leave it untouched
        # (its value is constant and uninteresting anyway).
        if isinstance(node.test, jast.Constant) and isinstance(
            node.test.value, jast.BoolLiteral
        ):
            return Injection()
        # A condition that assigns a variable used later (e.g.
        # `for (int b; destOffs < hi && (b = read0()) >= 0; )`) must stay native:
        # wrapping it in a call hides the assignment from Java's
        # definite-assignment analysis (a method call does not propagate the
        # "definitely assigned when true" flow), so the later use fails.
        if self.condition_extract.contains_assign(node.test):
            return Injection()
        event = ConditionEvent(
            self.file,
            node.test.lineno,
            self.event_id_generator.get_next_id(),
            jast.unparse(node.test),
            tmp_var=None,
        )
        call = jast.Member(
            value=jast.Name(id=java_lib_name),
            member=jast.Call(
                func=jast.Name(id=jast.identifier("evalCondition")),
                args=[jast.Constant(jast.IntLiteral(event.event_id)), node.test],
            ),
        )
        return Injection(assign=call, events=[event])

    def visit_If(self, node: jast.If):
        return self.visit_condition(node)

    def visit_While(self, node: jast.While):
        return self._inline_condition(node)

    def visit_DoWhile(self, node: jast.DoWhile):
        return self._inline_condition(node)

    def visit_For(self, node: jast.For):
        return self._inline_condition(node)


class LenEventFactory(DefEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addLenEvent")

    def get_event_call(self, event: LenEvent):
        # JLib.addLenEvent(eventID, varID, length), guarded by hasLen.  Build it
        # from the base call (eventID) rather than the Def call, which would add
        # the value/var arguments that addLenEvent does not take.
        call = JavaEventFactory.get_event_call(self, event)
        assert isinstance(call.value, jast.Member)
        assert isinstance(call.value.member, jast.Call)
        var = jast.Name(id=jast.identifier(event.var))
        call.value.member.args.append(java_lib_get_id(var))
        call.value.member.args.append(java_lib_get_len(var))
        return jast.If(
            test=java_lib_has_len(jast.Name(id=jast.identifier(event.var))),
            body=jast.Block(body=[call]),
        )

    def get_event(self, node: jast.stmt | jast.declaration, var: str):
        return LenEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), var
        )


def is_test(mod: jast.modifier):
    return (
        isinstance(mod, jast.Annotation)
        and len(mod.name.identifiers) == 1
        and mod.name.identifiers[0] == "Test"
    )


class TestStartEventFactory(FunctionEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addTestStartEvent")

    def visit_Method(self, node: jast.Method):
        if any(map(is_test, node.modifiers)):
            test_start_event = TestStartEvent(
                self.file,
                node.lineno,
                self.event_id_generator.get_next_id(),
                node.id.value,
                self.get_function_id(node),
            )
            return Injection(
                body=[
                    self.get_event_call(test_start_event),
                ],
                events=[test_start_event],
            )
        return Injection()


class TestEndEventFactory(FunctionEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addTestEndEvent")

    def visit_Method(self, node: jast.Method):
        if any(map(is_test, node.modifiers)):
            test_end_event = TestEndEvent(
                self.file,
                node.lineno,
                self.get_function_event_id(node),
                node.id.value,
                self.get_function_id(node),
            )
            return Injection(
                finalbody=[
                    self.get_event_call(test_end_event),
                ],
                events=[test_end_event],
            )
        return Injection()


class TestEventFactory(JavaEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        ignore_inner: bool = False,
        **kwargs,
    ):
        super().__init__(
            language, event_id_generator, function_id_generator, tmp_generator, **kwargs
        )
        self.ignore_inner = ignore_inner
        self.functions = 0
        self.classes = 0

    def enter_function(self, function):
        self.functions += 1

    def exit_function(self, function):
        self.functions -= 1

    def enter_class(self, class_):
        super().enter_class(class_)
        self.classes += 1

    def exit_class(self, class_):
        super().exit_class(class_)
        self.classes -= 1

    def visit(self, node):
        if self.ignore_inner and (self.functions > 1 or self.classes > 1):
            return Injection()
        return super().visit(node)


class TestLineEventFactory(LineEventFactory, TestEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addTestLineEvent")

    def get_event(self, node: jast.stmt):
        return TestLineEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id()
        )


class TestDefEventFactory(DefEventFactory, TestEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addTestDefEvent")

    def get_event(self, node: jast.stmt | jast.declaration, var: str):
        return TestDefEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), var
        )


class TestUseEventFactory(UseEventFactory, TestEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addTestUseEvent")

    def get_event(self, node: jast.stmt | jast.declaration, var: str):
        return TestUseEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), var
        )


class TestAssertEventFactory(TestEventFactory):
    def get_function(self) -> jast.identifier:
        return jast.identifier("addTestAssertEvent")

    def get_event(self, node: jast.stmt):
        return TestAssertEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id()
        )

    def visit_Assert(self, node):
        assert_event = self.get_event(node)
        return Injection(
            pre=[self.get_event_call(assert_event)],
            events=[assert_event],
        )

    def visit_Expr(self, node):
        call = node.value
        if isinstance(call, jast.Call) and "assert" in call.id:
            assert_event = self.get_event(node)
            return Injection(
                pre=[self.get_event_call(assert_event)],
                events=[assert_event],
            )
        return Injection()
