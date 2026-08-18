import ast
import copy
import typing
from ast import *

from sflkitlib.events.event import (
    LineEvent,
    Event,
    BranchEvent,
    DefEvent,
    FunctionEnterEvent,
    FunctionErrorEvent,
    FunctionExitEvent,
    LoopBeginEvent,
    LoopHitEvent,
    LoopEndEvent,
    UseEvent,
    ConditionEvent,
    ConditionValueEvent,
    LenEvent,
    TestStartEvent,
    TestEndEvent,
    TestLineEvent,
    TestDefEvent,
    TestUseEvent,
    TestAssertEvent,
)

from sflkit.language.meta import MetaVisitor, Injection, IDGenerator, TmpGenerator

#: Runtime module that provides the probe functions.
python_lib_module = "sflkitlib.lib"

#: Name the instrumented module binds the runtime to, and through which every
#: probe is called.
#:
#: Deliberately dunder-shaped. A module is free to tidy its own namespace, and
#: the common idiom keeps only dunders and its own submodules::
#:
#:     for varname in dir():                       # astropy/__init__.py
#:         if not ((varname.startswith('__') and varname.endswith('__')) or ...):
#:             del locals()[varname]
#:
#: A plain ``sflkitlib`` binding is deleted by that loop, and the next probe
#: raises ``NameError`` -- fatal for probes that are not inside a try/except
#: (function-enter, line, branch and loop events), which kills the import of the
#: package under test and truncates every trace at the same point. Binding
#: through a dunder name survives the idiom.
#:
#: Aliasing also shortens each probe from ``sflkitlib.lib.add_x(...)`` to
#: ``__sflkitlib__.add_x(...)``, one attribute lookup fewer on a path taken
#: millions of times per run.
python_lib = "__sflkitlib__"


def get_call(function, *args) -> Expr:
    return Expr(
        value=Call(
            func=Attribute(
                value=Name(
                    id=python_lib,  # enter lib
                ),
                attr=function,  # enter lib function
            ),
            args=[
                Constant(
                    value=argument,
                )
                for argument in args
            ],
            keywords=[],
        ),
    )


class PythonEventFactory(MetaVisitor, NodeVisitor):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        order: int = 0,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=order,
        )

    def visit_start(self, *args) -> Injection:
        return self.visit(*args)

    def generic_visit(self, node: AST) -> Injection:
        return Injection()

    def get_function(self):
        pass

    def get_event_call(self, event: Event):
        return get_call(self.get_function(), event.event_id)


class LineEventFactory(PythonEventFactory):
    def get_function(self):
        return "add_line_event"

    def visit_line(self, node: stmt) -> Injection:
        line_event = LineEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id()
        )
        return Injection(pre=[self.get_event_call(line_event)], events=[line_event])

    def visit_Assign(self, node: Assign) -> Injection:
        return self.visit_line(node)

    def visit_AnnAssign(self, node: AnnAssign) -> Injection:
        return self.visit_line(node)

    def visit_AugAssign(self, node: AugAssign) -> Injection:
        return self.visit_line(node)

    def visit_For(self, node: For) -> Injection:
        return self.visit_line(node)

    def visit_AsyncFor(self, node: AsyncFor) -> Injection:
        return self.visit_line(node)

    def visit_While(self, node: While) -> Injection:
        return self.visit_line(node)

    def visit_If(self, node: If) -> Injection:
        return self.visit_line(node)

    def visit_Try(self, node: Try) -> Injection:
        return self.visit_line(node)

    def visit_Return(self, node: Return) -> Injection:
        return self.visit_line(node)

    def visit_With(self, node: With) -> Injection:
        return self.visit_line(node)

    def visit_AsyncWith(self, node: AsyncWith) -> Injection:
        return self.visit_line(node)

    def visit_Import(self, node: Import) -> Injection:
        return self.visit_line(node)

    def visit_ImportFrom(self, node: ImportFrom) -> Injection:
        return self.visit_line(node)

    def visit_Delete(self, node: Delete) -> Injection:
        return self.visit_line(node)

    def visit_Raise(self, node: Raise) -> Injection:
        return self.visit_line(node)

    def visit_Assert(self, node: Assert) -> Injection:
        return self.visit_line(node)

    def visit_Global(self, node: Global) -> Injection:
        return self.visit_line(node)

    def visit_Nonlocal(self, node: Nonlocal) -> Injection:
        return self.visit_line(node)

    def visit_Expr(self, node: Expr) -> Injection:
        return self.visit_line(node)

    def visit_Pass(self, node: Pass) -> Injection:
        return self.visit_line(node)

    def visit_Break(self, node: Break) -> Injection:
        return self.visit_line(node)

    def visit_Continue(self, node: Continue) -> Injection:
        return self.visit_line(node)


class BranchEventFactory(PythonEventFactory):
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

    def get_function(self):
        return "add_branch_event"

    def _get_branch_events(self, node):
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

    def _visit_branch(self, node: typing.Union[If, While, For, AsyncFor]) -> Injection:
        then_branch_event, else_branch_event = self._get_branch_events(node)
        return Injection(
            body=[self.get_event_call(then_branch_event)],
            orelse=[self.get_event_call(else_branch_event)],
            events=[then_branch_event, else_branch_event],
        )

    def visit_For(self, node: For) -> Injection:
        return self._visit_branch(node)

    def visit_AsyncFor(self, node: AsyncFor) -> Injection:
        return self._visit_branch(node)

    def visit_While(self, node: While) -> Injection:
        return self._visit_branch(node)

    def visit_If(self, node: If) -> Injection:
        return self._visit_branch(node)

    def visit_ExceptHandler(self, node: ExceptHandler) -> Injection:
        branch_event = BranchEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.branch_id,
            -1,
        )
        return Injection(
            body=[self.get_event_call(branch_event)], events=[branch_event]
        )

    def visit_Try(self, node: Try) -> Injection:
        if node.handlers:
            else_branch_event = BranchEvent(
                self.file,
                node.lineno,
                self.event_id_generator.get_next_id(),
                self.branch_id,
                -1,
            )
            return Injection(
                orelse=[self.get_event_call(else_branch_event)],
                events=[else_branch_event],
            )
        else:
            return Injection()


class DefEventFactory(PythonEventFactory):
    def get_function(self):
        return "add_def_event"

    def get_event_call(self, event: DefEvent):
        call = get_call(self.get_function(), event.event_id)
        assert isinstance(call.value, Call)
        call.value.args.append(
            Call(
                func=Attribute(
                    value=Name(
                        id=python_lib,  # enter lib
                    ),
                    attr="get_id",  # enter lib function
                ),
                args=[Name(id=event.var)],
                keywords=[],
            )
        )
        call.value.args.append(
            Name(
                id=event.var,
            )
        )
        call.value.args.append(
            Call(
                func=Attribute(
                    value=Name(
                        id=python_lib,  # enter lib
                    ),
                    attr="get_type",  # enter lib function
                ),
                args=[Name(id=event.var)],
                keywords=[],
            )
        )
        return call

    def visit_function(
        self, node: typing.Union[FunctionDef, AsyncFunctionDef]
    ) -> Injection:
        def_events = list()
        for argument in self.variable_extract.visit(node.args):
            if argument != "self":
                def_events.append(self.get_event(node, argument))
        return Injection(
            body=[self.get_event_call(e) for e in def_events], events=def_events
        )

    def visit_FunctionDef(self, node: FunctionDef) -> Injection:
        return self.visit_function(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Injection:
        return self.visit_function(node)

    def get_event(
        self,
        node: typing.Union[
            Assign,
            AnnAssign,
            AugAssign,
            FunctionDef,
            AsyncFunctionDef,
            For,
            AsyncFor,
            With,
            AsyncWith,
        ],
        var: str,
    ):
        return DefEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), var
        )

    def visit_var_assign(
        self, node: typing.Union[Assign, AnnAssign, AugAssign], vars_: list
    ) -> Injection:
        def_events = list()
        for var in vars_:
            def_events.append(self.get_event(node, var))
        return Injection(
            post=[self.get_event_call(e) for e in def_events], events=def_events
        )

    def visit_Assign(self, node: Assign) -> Injection:
        vars_ = sum(
            [list(self.variable_extract.visit(target)) for target in node.targets],
            start=list(),
        )
        return self.visit_var_assign(node, vars_)

    def visit_AnnAssign(self, node: AnnAssign) -> Injection:
        if node.value is None:
            return Injection()
        else:
            vars_ = self.variable_extract.visit(node.target)
            return self.visit_var_assign(node, vars_)

    def visit_AugAssign(self, node: AugAssign) -> Injection:
        vars_ = self.variable_extract.visit(node.target)
        return self.visit_var_assign(node, vars_)

    def visit_for(self, node: typing.Union[For, AsyncFor]) -> Injection:
        vars_ = self.variable_extract.visit(node.target)
        def_events = list()
        for var in vars_:
            def_events.append(self.get_event(node, var))
        return Injection(
            body=[self.get_event_call(e) for e in def_events], events=def_events
        )

    def visit_For(self, node: For) -> Injection:
        return self.visit_for(node)

    def visit_AsyncFor(self, node: AsyncFor) -> Injection:
        return self.visit_for(node)

    def visit_with(self, node: With | AsyncWith):
        def_events = list()
        for item in node.items:
            if item.optional_vars:
                for var in self.variable_extract.visit(item.optional_vars):
                    def_events.append(self.get_event(node, var))
        if def_events:
            return Injection(
                body=[self.get_event_call(e) for e in def_events], events=def_events
            )
        return Injection()

    def visit_With(self, node: With) -> Injection:
        return self.visit_with(node)

    def visit_AsyncWith(self, node: AsyncWith) -> Injection:
        return self.visit_with(node)


class FunctionEventFactory(PythonEventFactory):
    functions: typing.Dict[AST, int] = dict()
    functions_exit_id: typing.Dict[AST, int] = dict()
    function_var: typing.Dict[AST, str] = dict()

    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        order: int,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=order,
            **kwargs,
        )
        self.function_stack = list()

    def get_function_id(self, node: AST) -> int:
        if node not in FunctionEventFactory.functions:
            FunctionEventFactory.functions[node] = (
                self.function_id_generator.get_next_id()
            )
        return FunctionEventFactory.functions[node]

    @staticmethod
    def get_function_event_id(node: AST, id_generator: IDGenerator) -> int:
        if node not in FunctionEventFactory.functions_exit_id:
            FunctionEventFactory.functions_exit_id[node] = id_generator.get_next_id()
        return FunctionEventFactory.functions_exit_id[node]

    @staticmethod
    def get_function_var(node: AST, tmp_generator: TmpGenerator) -> str:
        if node not in FunctionEventFactory.function_var:
            FunctionEventFactory.function_var[node] = tmp_generator.get_var_name()
        return FunctionEventFactory.function_var[node]

    def enter_function(self, function: AST):
        self.function_stack.append(function)

    def exit_function(self, function: AST):
        self.function_stack.pop()


class FunctionEnterEventFactory(FunctionEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=-2,
            **kwargs,
        )

    def get_function(self):
        return "add_function_enter_event"

    def visit_function(
        self, node: typing.Union[FunctionDef, AsyncFunctionDef]
    ) -> Injection:
        function_enter_event = FunctionEnterEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            node.name,
            self.get_function_id(node),
        )
        function_var = self.get_function_var(node, self.tmp_generator)
        return Injection(
            body=[
                self.get_event_call(function_enter_event),
                Assign(
                    targets=[
                        ast.Name(
                            id=function_var,
                        ),
                    ],
                    value=ast.Constant(value=None),
                    lineno=0,
                ),
            ],
            events=[function_enter_event],
        )

    def visit_FunctionDef(self, node: FunctionDef) -> Injection:
        return self.visit_function(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Injection:
        return self.visit_function(node)


class FunctionExitEventFactor(FunctionEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=2,
            **kwargs,
        )

    def get_function(self):
        return "add_function_exit_event"

    def get_event_call(self, event: FunctionExitEvent):
        call = get_call(
            self.get_function(),
            event.event_id,
        )
        assert isinstance(call.value, Call)
        call.value.args.append(Name(id=event.tmp_var))
        call.value.args.append(
            Call(
                func=Attribute(
                    value=Name(
                        id=python_lib,
                    ),
                    attr="get_type",  # enter lib function
                ),
                args=[
                    Name(
                        id=event.tmp_var,
                    )
                ],
                keywords=[],
            ),
        )
        return call

    def visit_function(
        self, node: typing.Union[FunctionDef, AsyncFunctionDef]
    ) -> Injection:
        function_exit_event = FunctionExitEvent(
            self.file,
            node.lineno,
            self.get_function_event_id(node, self.event_id_generator),
            node.name,
            self.get_function_id(node),
            tmp_var=self.get_function_var(node, self.tmp_generator),
        )
        return Injection(
            body_last=[self.get_event_call(function_exit_event)],
            events=[function_exit_event],
        )

    def visit_FunctionDef(self, node: FunctionDef) -> Injection:
        return self.visit_function(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Injection:
        return self.visit_function(node)

    def visit_Return(self, node: Return) -> Injection:
        function = self.function_stack[-1]
        function_var = self.get_function_var(function, self.tmp_generator)
        function_exit_event = FunctionExitEvent(
            self.file,
            node.lineno,
            self.get_function_event_id(node, self.event_id_generator),
            function.name,
            self.get_function_id(function),
            tmp_var=function_var,
        )
        return Injection(
            pre=[
                Assign(
                    targets=[
                        ast.Name(
                            id=function_var,
                        ),
                    ],
                    value=node.value if node.value else ast.Constant(value=None),
                    lineno=0,
                ),
                self.get_event_call(function_exit_event),
            ],
            assign=ast.Name(id=function_var),
            events=[function_exit_event],
        )


class FunctionErrorEventFactory(FunctionEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=2,
            **kwargs,
        )

    def get_function(self):
        return "add_function_error_event"

    def visit_function(
        self, node: typing.Union[FunctionDef, AsyncFunctionDef]
    ) -> Injection:
        function_error_event = FunctionErrorEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            node.name,
            self.get_function_id(node),
        )
        return Injection(
            error=[self.get_event_call(function_error_event)],
            events=[function_error_event],
        )

    def visit_FunctionDef(self, node: FunctionDef) -> Injection:
        return self.visit_function(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Injection:
        return self.visit_function(node)


class LoopEventFactory(PythonEventFactory):
    loops: typing.Dict[AST, int] = dict()
    loop_id: int = 0

    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        order: int,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=order,
            **kwargs,
        )

    @staticmethod
    def get_loop_id(node: AST) -> int:
        if node not in LoopEventFactory.loops:
            LoopEventFactory.loops[node] = LoopEventFactory.loop_id
            LoopEventFactory.loop_id += 1
        return LoopEventFactory.loops[node]

    def visit_loop(self, node: typing.Union[For, AsyncFor, While]) -> Injection:
        pass

    def visit_For(self, node: For) -> Injection:
        return self.visit_loop(node)

    def visit_AsyncFor(self, node: AsyncFor) -> Injection:
        return self.visit_loop(node)

    def visit_While(self, node: While) -> Injection:
        return self.visit_loop(node)


class LoopBeginEventFactory(LoopEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=-1,
            **kwargs,
        )

    def get_function(self):
        return "add_loop_begin_event"

    def visit_loop(self, node: typing.Union[For, AsyncFor, While]) -> Injection:
        loop_begin_event = LoopBeginEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.get_loop_id(node),
        )
        return Injection(
            pre=[self.get_event_call(loop_begin_event)], events=[loop_begin_event]
        )


class LoopHitEventFactory(LoopEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=-1,
            **kwargs,
        )

    def get_function(self):
        return "add_loop_hit_event"

    def visit_loop(self, node: typing.Union[For, AsyncFor, While]) -> Injection:
        loop_hit_event = LoopHitEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.get_loop_id(node),
        )
        return Injection(
            body=[self.get_event_call(loop_hit_event)], events=[loop_hit_event]
        )


class LoopEndEventFactory(LoopEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=1,
            **kwargs,
        )

    def get_function(self):
        return "add_loop_end_event"

    def visit_loop(self, node: typing.Union[For, AsyncFor, While]) -> Injection:
        loop_end_event = LoopEndEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            self.get_loop_id(node),
        )
        return Injection(
            finalbody=[self.get_event_call(loop_end_event)], events=[loop_end_event]
        )


class UseEventFactory(PythonEventFactory):
    def get_function(self):
        return "add_use_event"

    def _get_try_wrapper(self, event: UseEvent):
        return Try(
            body=[self._get_wrapped_property(event)],
            handlers=[
                ExceptHandler(
                    # Any exception, not a hand-picked few. Evaluating a probe's
                    # own arguments runs subject code -- len(x) on a lazy proxy,
                    # attribute access through __getattribute__ -- which can
                    # raise anything. Django's settings object raises
                    # ImproperlyConfigured when touched before configuration, so
                    # a narrow guard let a probe abort the import of the package
                    # under test and truncate every trace at the same point.
                    # A probe must never change what the program does.
                    type=Name(id="Exception"),
                    name=None,
                    body=[Pass()],
                ),
            ],
            orelse=[],
            finalbody=[],
        )

    def _get_std_call(self, event: UseEvent):
        call = get_call(self.get_function(), event.event_id)
        assert isinstance(call.value, Call)
        call.value.args.append(
            Call(
                func=Attribute(
                    value=Name(
                        id=python_lib,  # enter lib
                    ),
                    attr="get_id",  # enter lib function
                ),
                args=[Name(id=event.var)],
                keywords=[],
            )
        )
        return call

    @staticmethod
    def _get_type_of(class_: str) -> Call:
        """
        Build ``type(<class_>)``.

        Deliberately ``type(x)`` and not ``x.__class__``: the two agree for
        ordinary objects, but ``__class__`` is a normal attribute lookup and can
        itself be a property. Django's lazy objects define
        ``__class__ = property(new_method_proxy(...))``, so reading it re-enters
        the proxy machinery this guard is meant to stay out of, recursing until
        the stack is exhausted. ``type()`` reads the type slot directly and
        cannot be proxied -- django's own source makes the same point: "We have
        to use type(self), not self.__class__, because the latter is proxied."
        """
        return Call(func=Name(id="type"), args=[Name(id=class_)], keywords=[])

    def _get_wrapped_property(self, event: UseEvent):
        body = self._get_std_call(event)
        attributes = event.var.split(".")
        for i in range(len(attributes) - 1):
            class_ = ".".join(attributes[: -1 - i])
            attribute = attributes[-1 - i]
            body = If(
                test=BoolOp(
                    op=Or(),
                    values=[
                        UnaryOp(
                            op=Not(),
                            operand=Call(
                                func=Name(
                                    id="hasattr",
                                ),
                                args=[
                                    self._get_type_of(class_),
                                    Constant(
                                        value=attribute,
                                    ),
                                ],
                                keywords=[],
                            ),
                        ),
                        UnaryOp(
                            op=Not(),
                            operand=Call(
                                func=Name(
                                    id="isinstance",
                                ),
                                args=[
                                    Attribute(
                                        value=self._get_type_of(class_),
                                        attr=attribute,
                                        ctx=Load(),
                                    ),
                                    Name(
                                        id="property",
                                    ),
                                ],
                                keywords=[],
                            ),
                        ),
                    ],
                ),
                body=[body],
                orelse=[],
            )
        return body

    def get_event_call(self, event: UseEvent):
        return self._get_try_wrapper(event)

    def get_event(self, node: AST, use: str) -> UseEvent:
        # noinspection PyUnresolvedReferences
        return UseEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), use
        )

    def visit_use(self, node: AST):
        uses = self.use_extract.visit(node)
        use_events = list()
        for use in uses:
            use_events.append(self.get_event(node, use))
        return Injection(
            pre=[self.get_event_call(e) for e in use_events], events=use_events
        )

    def visit_Assign(self, node: Assign) -> Injection:
        return self.visit_use(node.value)

    def visit_AnnAssign(self, node: AnnAssign) -> Injection:
        if node.value is None:
            return Injection()
        else:
            return self.visit_use(node.value)

    def visit_AugAssign(self, node: AugAssign) -> Injection:
        return self.visit_use(node.target) + self.visit_use(node.value)

    def visit_loop(self, node: AST):
        injection = self.visit_use(node)
        if isinstance(node, While):
            injection.body_last = injection.pre
        return injection

    def visit_For(self, node: For) -> Injection:
        return self.visit_loop(node.iter)

    def visit_AsyncFor(self, node: AsyncFor) -> Injection:
        return self.visit_loop(node.iter)

    def visit_While(self, node: While) -> Injection:
        return self.visit_loop(node.test)

    def visit_If(self, node: If) -> Injection:
        return self.visit_use(node.test)

    def visit_Return(self, node: Return) -> Injection:
        return self.visit_use(node.value)

    def visit_With(self, node: With) -> Injection:
        return sum(
            [self.visit_use(item.context_expr) for item in node.items],
            start=Injection(),
        )

    def visit_AsyncWith(self, node: AsyncWith) -> Injection:
        return sum(
            [self.visit_use(item.context_expr) for item in node.items],
            start=Injection(),
        )

    def visit_Delete(self, node: Delete) -> Injection:
        return sum(
            [self.visit_use(target) for target in node.targets], start=Injection()
        )

    def visit_Raise(self, node: Raise) -> Injection:
        return self.visit_use(node.exc)

    def visit_Assert(self, node: Assert) -> Injection:
        return self.visit_use(node.test)

    def visit_Expr(self, node: Expr) -> Injection:
        return self.visit_use(node.value)

    def visit_Global(self, node: Global) -> Injection:
        injection = self.visit_use(node)
        injection.post = injection.pre
        injection.pre = list()
        return injection

    def visit_Nonlocal(self, node: Nonlocal) -> Injection:
        injection = self.visit_use(node)
        injection.post = injection.pre
        injection.pre = list()
        return injection


class ConditionEventFactory(PythonEventFactory):
    def get_function(self):
        return "add_condition_event"

    def get_event_call(self, event: ConditionEvent):
        call = get_call(
            self.get_function(),
            event.event_id,
        )
        assert isinstance(call.value, Call)
        call.value.args.append(
            Name(
                id=event.tmp_var,
            )
        )
        return call

    def visit_condition(self, node: typing.Union[If, While]) -> Injection:
        self.condition_extract.setup(self)
        var, var_use, var_assign, events = self.condition_extract.visit(node.test)
        return Injection(pre=[var_assign], assign=var_use, events=events)

    def visit_While(self, node: While) -> Injection:
        injection = self.visit_condition(node)
        injection.body_last = injection.pre
        return injection

    def visit_If(self, node: If) -> Injection:
        return self.visit_condition(node)


class ConditionValueEventFactory(PythonEventFactory):
    """Emit a branch-distance companion event for single-comparison conditions.

    For an ``if``/``while`` whose test is a lone comparison ``lhs <op> rhs`` with
    side-effect-free operands, inject a call that reports the operands to the
    runtime, which computes the branch distance. The original test is left
    untouched (the plain :class:`ConditionEventFactory` still records its
    boolean), so this is purely additive; compound tests, non-comparison tests,
    and tests with side-effecting operands are skipped and fall back to the
    boolean condition event plus approach-level guidance.
    """

    _OPS = {
        ast.Lt: "<",
        ast.LtE: "<=",
        ast.Gt: ">",
        ast.GtE: ">=",
        ast.Eq: "==",
        ast.NotEq: "!=",
    }

    def get_function(self):
        return "add_condition_value_event"

    @staticmethod
    def _is_pure(node: AST) -> bool:
        # Operands we can safely re-evaluate: no calls, subscripts, or operators
        # that could have side effects.
        if isinstance(node, Constant):
            return True
        if isinstance(node, Name):
            return True
        if isinstance(node, Attribute):
            return ConditionValueEventFactory._is_pure(node.value)
        if isinstance(node, UnaryOp) and isinstance(node.op, (UAdd, USub)):
            return ConditionValueEventFactory._is_pure(node.operand)
        return False

    def _capturable(self, test: AST):
        if not isinstance(test, Compare) or len(test.ops) != 1:
            return None
        op = self._OPS.get(type(test.ops[0]))
        if op is None:
            return None
        lhs, rhs = test.left, test.comparators[0]
        if not (self._is_pure(lhs) and self._is_pure(rhs)):
            return None
        return op, lhs, rhs

    def _get_event_call(self, event: ConditionValueEvent, op: str, lhs, rhs):
        # sflkitlib.lib.add_condition_value_event(event_id, lhs, rhs, "op")
        call = get_call(self.get_function(), event.event_id)
        assert isinstance(call.value, Call)
        call.value.args.append(copy.deepcopy(lhs))
        call.value.args.append(copy.deepcopy(rhs))
        call.value.args.append(Constant(value=op))
        return call

    def visit_condition(self, node: typing.Union[If, While]) -> Injection:
        capturable = self._capturable(node.test)
        if capturable is None:
            return Injection()
        op, lhs, rhs = capturable
        event = ConditionValueEvent(
            self.file,
            node.lineno,
            self.event_id_generator.get_next_id(),
            ast.unparse(node.test),
            op,
        )
        return Injection(
            pre=[self._get_event_call(event, op, lhs, rhs)], events=[event]
        )

    def visit_If(self, node: If) -> Injection:
        return self.visit_condition(node)

    def visit_While(self, node: While) -> Injection:
        injection = self.visit_condition(node)
        injection.body_last = injection.pre
        return injection


class LenEventFactory(DefEventFactory):
    def get_function(self):
        return "add_len_event"

    def get_check_for_len(self, event: LenEvent):
        call = get_call(self.get_function(), event.event_id)
        assert isinstance(call.value, Call)
        call.value.args.append(
            Call(
                func=Attribute(
                    value=Name(
                        id=python_lib,  # enter lib
                    ),
                    attr="get_id",  # enter lib function
                ),
                args=[Name(id=event.var)],
                keywords=[],
            )
        )
        call.value.args.append(
            Call(
                func=Name(id="len"),
                args=[Name(id=event.var)],
                keywords=[],
            )
        )
        return Try(
            body=[call],
            handlers=[
                ExceptHandler(
                    # Any exception, not a hand-picked few. Evaluating a probe's
                    # own arguments runs subject code -- len(x) on a lazy proxy,
                    # attribute access through __getattribute__ -- which can
                    # raise anything. Django's settings object raises
                    # ImproperlyConfigured when touched before configuration, so
                    # a narrow guard let a probe abort the import of the package
                    # under test and truncate every trace at the same point.
                    # A probe must never change what the program does.
                    type=Name(id="Exception"),
                    name=None,
                    body=[Pass()],
                )
            ],
            orelse=[],
            finalbody=[],
        )

    def get_event_call(self, event: LenEvent):
        return self.get_check_for_len(event)

    def get_event(self, node: typing.Union[Assign, AnnAssign, AugAssign], var: str):
        return LenEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), var
        )


class TestStartEventFactory(FunctionEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=2,
            **kwargs,
        )

    def get_function(self):
        return "add_test_start_event"

    def visit_function(
        self, node: typing.Union[FunctionDef, AsyncFunctionDef]
    ) -> Injection:
        if node.name.lower().startswith("test"):
            test_start_event = TestStartEvent(
                self.file,
                node.lineno,
                self.event_id_generator.get_next_id(),
                node.name,
                self.get_function_id(node),
            )
            return Injection(
                body=[
                    self.get_event_call(test_start_event),
                ],
                events=[test_start_event],
            )
        return Injection()

    def visit_FunctionDef(self, node: FunctionDef) -> Injection:
        return self.visit_function(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Injection:
        return self.visit_function(node)


class TestEndEventFactory(FunctionEventFactory):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
            order=2,
            **kwargs,
        )

    def get_function(self):
        return "add_test_end_event"

    def visit_function(
        self, node: typing.Union[FunctionDef, AsyncFunctionDef]
    ) -> Injection:
        if node.name.lower().startswith("test"):
            test_end_event = TestEndEvent(
                self.file,
                node.lineno,
                self.event_id_generator.get_next_id(),
                node.name,
                self.get_function_id(node),
            )
            return Injection(
                finalbody=[self.get_event_call(test_end_event)],
                events=[test_end_event],
            )
        return Injection()

    def visit_FunctionDef(self, node: FunctionDef) -> Injection:
        return self.visit_function(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Injection:
        return self.visit_function(node)


class TestLineEventFactory(LineEventFactory):
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
        self.classes_in_functions = 0

    def enter_function(self, function):
        self.functions += 1

    def exit_function(self, function):
        self.functions -= 1

    def enter_class(self, class_):
        if self.functions > 0:
            self.classes_in_functions += 1
        else:
            self.classes += 1

    def exit_class(self, class_):
        if self.functions > 0:
            self.classes_in_functions -= 1
        else:
            self.classes -= 1

    def get_function(self):
        return "add_test_line_event"

    def visit_line(self, node: AST) -> Injection:
        # noinspection PyUnresolvedReferences
        line_event = TestLineEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id()
        )
        return Injection(pre=[self.get_event_call(line_event)], events=[line_event])

    def visit(self, node):
        if self.ignore_inner and (
            self.functions > 1 or self.classes_in_functions > 0 or self.classes > 1
        ):
            return Injection()
        return super().visit(node)


class TestDefEventFactory(DefEventFactory):
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
        self.classes_in_functions = 0

    def enter_function(self, function):
        self.functions += 1

    def exit_function(self, function):
        self.functions -= 1

    def enter_class(self, class_):
        if self.functions > 0:
            self.classes_in_functions += 1
        else:
            self.classes += 1

    def exit_class(self, class_):
        if self.functions > 0:
            self.classes_in_functions -= 1
        else:
            self.classes -= 1

    def get_function(self):
        return "add_test_def_event"

    def get_event(self, node: typing.Union[Assign, AnnAssign, AugAssign], var: str):
        return TestDefEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), var
        )

    def get_event_call(self, event: TestDefEvent):
        call = get_call(self.get_function(), event.event_id)
        assert isinstance(call.value, Call)
        call.value.args.append(
            Call(
                func=Attribute(
                    value=Name(
                        id=python_lib,  # enter lib
                    ),
                    attr="get_id",  # enter lib function
                ),
                args=[Name(id=event.var)],
                keywords=[],
            )
        )
        return call

    def visit(self, node):
        if self.ignore_inner and (
            self.functions > 1 or self.classes_in_functions > 0 or self.classes > 1
        ):
            return Injection()
        return super().visit(node)


class TestUseEventFactory(UseEventFactory):
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
        self.classes_in_functions = 0

    def enter_function(self, function):
        self.functions += 1

    def exit_function(self, function):
        self.functions -= 1

    def enter_class(self, class_):
        if self.functions > 0:
            self.classes_in_functions += 1
        else:
            self.classes += 1

    def exit_class(self, class_):
        if self.functions > 0:
            self.classes_in_functions -= 1
        else:
            self.classes -= 1

    def get_function(self):
        return "add_test_use_event"

    def get_event(self, node: AST, use: str) -> TestUseEvent:
        # noinspection PyUnresolvedReferences
        return TestUseEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id(), use
        )

    def visit(self, node):
        if self.ignore_inner and (
            self.functions > 1 or self.classes_in_functions > 0 or self.classes > 1
        ):
            return Injection()
        return super().visit(node)


class TestAssertEventFactory(PythonEventFactory):
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
        self.classes_in_functions = 0

    def enter_function(self, function):
        self.functions += 1

    def exit_function(self, function):
        self.functions -= 1

    def enter_class(self, class_):
        if self.functions > 0:
            self.classes_in_functions += 1
        else:
            self.classes += 1

    def exit_class(self, class_):
        if self.functions > 0:
            self.classes_in_functions -= 1
        else:
            self.classes -= 1

    def get_function(self):
        return "add_test_assert_event"

    def get_event_call(self, event: Event):
        return get_call(self.get_function(), event.event_id)

    def visit_Assert(self, node: Assert) -> Injection:
        assert_event = TestAssertEvent(
            self.file, node.lineno, self.event_id_generator.get_next_id()
        )
        return Injection(pre=[self.get_event_call(assert_event)], events=[assert_event])

    def visit_Expr(self, node: Expr) -> Injection:
        if isinstance(node.value, Call):
            func = ast.unparse(node.value.func)
            if "assert" in func:
                assert_event = TestAssertEvent(
                    self.file, node.lineno, self.event_id_generator.get_next_id()
                )
                return Injection(
                    pre=[self.get_event_call(assert_event)], events=[assert_event]
                )
        return Injection()

    def visit(self, node):
        if self.ignore_inner and (
            self.functions > 1 or self.classes_in_functions > 0 or self.classes > 1
        ):
            return Injection()
        return super().visit(node)
