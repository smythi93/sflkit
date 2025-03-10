import random
from abc import ABC
from typing import List, Type, Any

from sflkitlib.events.event import Event


class Injection:
    def __init__(
        self,
        pre: List = None,
        body: List = None,
        body_last: List = None,
        orelse: List = None,
        finalbody: List = None,
        error: List = None,
        post: List = None,
        assign: Any = None,
        pre_block: List = None,
        post_block: List = None,
        static_pre_block: List = None,
        static_post_block: List = None,
        events: List[Event] = None,
    ):
        self.pre = pre or []
        self.body = body or []
        self.body_last = body_last or []
        self.orelse = orelse or []
        self.finalbody = finalbody or []
        self.error = error or []
        self.post = post or []
        self.assign = assign
        self.pre_block = pre_block or []
        self.post_block = post_block or []
        self.static_pre_block = static_pre_block or []
        self.static_post_block = static_post_block or []
        self.events = events or []

    def __add__(self, other):
        if isinstance(other, Injection):
            return Injection(
                self.pre + other.pre,
                self.body + other.body,
                self.body_last + other.body_last,
                self.orelse + other.orelse,
                self.finalbody + other.finalbody,
                self.error + other.error,
                self.post + other.post,
                self.assign if self.assign else other.assign,
                self.pre_block + other.pre_block,
                self.post_block + other.post_block,
                self.static_pre_block + other.static_pre_block,
                self.static_post_block + other.static_post_block,
                self.events + other.events,
            )
        else:
            raise TypeError("Can add Injection only to other Injections")


class IDGenerator:
    def __init__(self):
        self.current_id = 0

    def get_next_id(self):
        id_ = self.current_id
        self.current_id += 1
        return id_


class TmpGenerator:
    def __init__(self):
        self._tmp_count = 0
        self.random = random.randbytes(4).hex()

    def get_var_name(self):
        var = f"sk_tmp_{self.random}_{self._tmp_count}"
        self._tmp_count += 1
        return var


class MetaVisitor(ABC):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        **kwargs,
    ):
        self.event_id_generator = event_id_generator
        self.function_id_generator = function_id_generator
        self.tmp_generator = tmp_generator
        self.variable_extract = language.var_extract
        self.use_extract = language.use_extract
        self.condition_extract = language.condition_extract
        self.event_count = 0
        self.file = None

    def get_event_call(self, event: Event):
        pass

    def enter_function(self, function):
        pass

    def exit_function(self, function):
        pass

    def enter_block(self, block):
        pass

    def exit_block(self, block):
        pass

    def enter_class(self, class_):
        pass

    def exit_class(self, class_):
        pass

    def enter_file(self, file):
        self.file = file

    def exit_file(self, file):
        pass

    def visit_start(self, *args) -> Injection:
        pass


class CombinationVisitor(MetaVisitor):
    def __init__(
        self,
        language,
        event_id_generator: IDGenerator,
        function_id_generator: IDGenerator,
        tmp_generator: TmpGenerator,
        visitors: List[Type[MetaVisitor]],
        test: bool = False,
        ignore_inner: bool = False,
    ):
        super().__init__(
            language,
            event_id_generator,
            function_id_generator,
            tmp_generator,
        )
        if test:
            self.visitors = [
                visitor(
                    language,
                    event_id_generator,
                    function_id_generator,
                    tmp_generator,
                    ignore_inner=ignore_inner,
                )
                for visitor in visitors
            ]
        else:
            self.visitors = [
                visitor(
                    language,
                    event_id_generator,
                    function_id_generator,
                    tmp_generator,
                )
                for visitor in visitors
            ]

    def visit_start(self, *args) -> Injection:
        injections = Injection()
        for visitor in self.visitors:
            i = visitor.visit_start(*args)
            injections += i
        return injections

    def enter_function(self, function):
        for visitor in self.visitors:
            visitor.enter_function(function)

    def exit_function(self, function):
        for visitor in self.visitors:
            visitor.exit_function(function)

    def enter_block(self, block):
        for visitor in self.visitors:
            visitor.enter_block(block)

    def exit_block(self, block):
        for visitor in self.visitors:
            visitor.exit_block(block)

    def enter_class(self, class_):
        for visitor in self.visitors:
            visitor.enter_class(class_)

    def exit_class(self, class_):
        for visitor in self.visitors:
            visitor.exit_class(class_)

    def enter_file(self, file):
        for visitor in self.visitors:
            visitor.enter_file(file)

    def exit_file(self, file):
        for visitor in self.visitors:
            visitor.exit_file(file)
