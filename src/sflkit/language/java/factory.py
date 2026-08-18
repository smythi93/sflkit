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
        line_event = LineEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id()
        )
        is_static = any(isinstance(mod, jast.Static) for mod in node.modifiers)
        if is_static:
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

    def _visit_loop(self, node: jast.For | jast.ForEach | jast.While | jast.DoWhile):
        then_branch_event, else_branch_event = self._get_branch_events(node)
        return Injection(
            body=[self.get_event_call(then_branch_event)],
            post=[self.get_event_call(else_branch_event)],
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
        def_events = []
        for var in node.declarators:
            def_events.append(self.get_event(node, var.id.id.value))
        return Injection(
            post=[self.get_event_call(event) for event in def_events],
            events=def_events,
        )

    def visit_Field(self, node: jast.Field):
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
            return Injection(
                static_post_block=[self.get_event_call(event) for event in def_events],
                events=def_events,
            )
        return Injection(
            post_block=[self.get_event_call(event) for event in def_events],
            events=def_events,
        )

    def visit_For(self, node: jast.For):
        if node.init:
            if isinstance(node.init, jast.LocalVariable):
                return self.visit_LocalVariable(node.init)
            else:
                injection = Injection()
                for var in node.init:
                    injection += self.visit(var)
                return Injection(
                    body=injection.post,
                    events=injection.events,
                )
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
            # fall-through (explicit `return;` are handled by visit_Return).
            if self.return_visitor.visit(node):
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
        if not self.return_visitor.visit(node):
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

    def visit_use(self, node: jast.stmt | jast.declaration):
        uses = self.use_extract.visit(node)
        use_events = []
        for use in uses:
            use_events.append(self.get_event(node, use))
        return Injection(
            pre=[self.get_event_call(event) for event in use_events],
            events=use_events,
        )

    def visit_Field(self, node):
        injection = self.visit_use(node)
        is_static = any(isinstance(mod, jast.Static) for mod in node.modifiers)
        if is_static:
            return Injection(
                static_pre_block=injection.pre,
                events=injection.events,
            )
        return Injection(
            pre_block=injection.pre,
            events=injection.events,
        )

    def visit_If(self, node: jast.If):
        return self.visit_use(node.test)

    def visit_Switch(self, node: jast.Switch):
        return self.visit_use(node.value)

    def visit_For(self, node: jast.For):
        injection = Injection()
        if node.init:
            if isinstance(node.init, jast.LocalVariable):
                injection += self.visit_use(node.init)
            else:
                for var in node.init:
                    injection += self.visit_use(var)
        update = Injection()
        if node.update:
            for var in node.update:
                update += self.visit_use(var)
        test = Injection()
        if node.test:
            test += self.visit_use(node.test)
        return Injection(
            pre=injection.pre + test.pre,
            body_last=update.pre + test.pre,
            events=injection.events + test.events + update.events,
        )

    def visit_ForEach(self, node: jast.ForEach):
        return self.visit_use(node.iter)

    def visit_While(self, node: jast.While):
        injection = self.visit_use(node.test)
        return Injection(
            pre=injection.pre,
            body_last=injection.pre,
            events=injection.events,
        )

    def visit_DoWhile(self, node: jast.DoWhile):
        injection = self.visit_use(node.test)
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
        if node.test:
            self.condition_extract.setup(self)
            var, var_use, var_assign, events = self.condition_extract.visit(node.test)
            return Injection(
                pre=[var_assign],
                assign=var_use,
                events=events,
            )
        return Injection()

    @staticmethod
    def _to_reassignment(node):
        """Turn tmp-var *declarations* in a condition setup into *assignments*.

        The condition tmp var is declared once before the loop (``pre``); inside
        the loop body it must be re-assigned rather than re-declared, otherwise
        the declaration shadows the outer one (a Java compile error).
        """
        if isinstance(node, jast.Compound):
            return jast.Compound(
                body=[
                    ConditionEventFactory._to_reassignment(s) for s in node.body
                ]
            )
        if isinstance(node, jast.LocalVariable) and node.declarators[0].init is not None:
            declarator = node.declarators[0]
            return jast.Expr(
                value=jast.Assign(
                    target=jast.Name(id=declarator.id.id), value=declarator.init
                )
            )
        return node

    @staticmethod
    def _bare_declarations(node):
        """Bare ``boolean tmp;`` declarations for every tmp a condition setup
        declares, so they can be hoisted before a do-while loop."""
        decls = []
        if isinstance(node, (jast.Compound, jast.Block)):
            for stmt in node.body:
                decls.extend(ConditionEventFactory._bare_declarations(stmt))
        elif isinstance(node, jast.If):
            decls.extend(ConditionEventFactory._bare_declarations(node.body))
            if node.orelse is not None:
                decls.extend(ConditionEventFactory._bare_declarations(node.orelse))
        elif isinstance(node, jast.LocalVariable):
            for declarator in node.declarators:
                decls.append(
                    jast.LocalVariable(
                        type=jast.Boolean(),
                        declarators=[
                            jast.declarator(
                                id=jast.variabledeclaratorid(id=declarator.id.id)
                            )
                        ],
                    )
                )
        return decls

    def visit_If(self, node: jast.If):
        return self.visit_condition(node)

    def visit_While(self, node: jast.While):
        injection = self.visit_condition(node)
        injection.body_last = [self._to_reassignment(s) for s in injection.pre]
        return injection

    def visit_DoWhile(self, node: jast.DoWhile):
        injection = self.visit_condition(node)
        if injection.pre:
            # do { ... } while (cond): the temp is used by the trailing `while`,
            # so declare it before the loop and (re)assign it inside the body.
            var_assign = injection.pre[0]
            injection.pre = self._bare_declarations(var_assign)
            injection.body_last = [self._to_reassignment(var_assign)]
        return injection

    def visit_For(self, node: jast.For):
        injection = self.visit_condition(node)
        injection.body_last = [self._to_reassignment(s) for s in injection.pre]
        return injection


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
        self.classes += 1

    def exit_class(self, class_):
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
