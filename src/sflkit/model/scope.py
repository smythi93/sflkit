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
        #: Bumped whenever the *names and types* bound in this scope change --
        #: not when a variable is merely reassigned. Analyses that depend only
        #: on which names of which types are in scope (ScalarPairFactory being
        #: the expensive one) can cache their result against
        #: :meth:`type_signature` and stay correct while a loop reassigns the
        #: same variables over and over, which is the common case.
        self.type_version = 0

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
        previous = self.variables.get(var)
        if previous is None or previous.type_ != type_:
            self.type_version += 1
        self.variables[var] = Var(var, value, type_, id_)

    def type_signature(self, include_root: bool = True) -> tuple:
        """
        Identify the name-and-type bindings visible from this scope.

        Two scopes with equal signatures make every name of every type resolve
        the same way, and -- because ``get_all_vars_dict`` fills from the
        outermost scope inward and a repeat binding keeps its original slot --
        in the same order. The signature walks the chain, so it costs the
        nesting depth rather than the number of variables in scope; at a
        definition there are commonly a couple of hundred of the latter and a
        handful of the former.

        :param include_root: When ``False`` the outermost scope is left out,
            matching :meth:`get_local_vars`. A caller that ignores the globals
            must also ignore their versions, or module-level execution -- which
            keeps binding new names throughout a run -- would invalidate its
            cache on bindings it never looked at.
        :returns: A hashable identity for the visible bindings.
        """
        signature = []
        current = self
        while current is not None:
            if not include_root and current.parent is None:
                break
            signature.append(current.id)
            signature.append(current.type_version)
            current = current.parent
        return tuple(signature)

    def get_all_vars_dict(self):
        # Walk to the root once, then fill a single dict from the outermost
        # scope inward so inner definitions overwrite outer ones. The previous
        # form built a whole new dict at every level
        # (``variables = {**current.variables, **variables}``), making this
        # O(depth x variables) in allocations; it is the hottest call in tree
        # building because ScalarPairFactory asks for the scope's variables on
        # every DEF event.
        chain = []
        current = self
        while current is not None:
            chain.append(current)
            current = current.parent
        variables = dict()
        for scope in reversed(chain):
            variables.update(scope.variables)
        return variables

    def get_all_vars(self) -> List[Var]:
        return list(self.get_all_vars_dict().values())

    def get_local_vars(self) -> List[Var]:
        """
        The variables visible here except those bound by the outermost scope.

        The outermost scope is where module-level execution accumulates: on a
        real library that is the whole imported namespace -- version strings,
        settings dictionaries, lookup tables -- and it dwarfs what a function
        actually has in hand. Analyses that relate a definition to its
        surroundings want the surroundings, not the module's namespace.

        Order matches :meth:`get_all_vars` for the scopes it does include.

        :returns: The visible variables, outermost scope excluded.
        """
        chain = []
        current = self
        while current is not None and current.parent is not None:
            chain.append(current)
            current = current.parent
        variables = dict()
        for scope in reversed(chain):
            variables.update(scope.variables)
        return list(variables.values())
