from threading import Lock
from typing import List


class Var(object):
    def __init__(self, var, value, type_, id_: int = None):
        self.var = var
        self.value = value
        self.type_ = type_
        self.id = id_ if id_ is not None else hash(self)

    def __hash__(self):
        return hash(self.var)

    def __eq__(self, other):
        return isinstance(other, Var) and self.var == other.var


class IDGenerator:
    def __init__(self):
        self.current_id = 0
        self.lock = Lock()

    def get_next_id(self):
        with self.lock:
            self.current_id += 1
            return self.current_id


class Scope(object):

    SCOPE_ID = IDGenerator()

    def __init__(self, parent=None):
        self.parent = parent
        self.variables = dict()
        self.id = Scope.SCOPE_ID.get_next_id()

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Scope) and self.id == other.id

    def enter(self):
        return Scope(parent=self)

    def exit(self):
        if self.parent is not None:
            return self.parent
        else:
            return self

    def __contains__(self, var: str) -> bool:
        current = self
        while current is not None:
            if var in current.variables:
                return True
            current = current.parent
        return False

    def value(self, var: str) -> Var:
        current = self
        while current is not None:
            if var in current.variables:
                return current.variables[var].value
            current = current.parent
        return None

    def add(self, var, value, type_, id_: int = None):
        self.variables[var] = Var(var, value, type_, id_)

    def get_all_vars_dict(self):
        current = self
        variables = dict()
        while current is not None:
            variables = {**current.variables, **variables}
            current = current.parent
        return variables

    def get_all_vars(self) -> List[Var]:
        return list(self.get_all_vars_dict().values())
