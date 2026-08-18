"""
A call tree that can be merged across processes.

Collectors run inside the test process, so every test produces its own tree and
the parent has to combine them. Combining is only cheap if a node's
observations are comparable without shipping the objects they were derived
from, which is why observations are recorded as ``{feature id: value}`` rather
than as :class:`~sflkit.features.value.Feature` objects: a feature holds a
reference to its analysis object, and pickling one drags the whole analysis
graph across the process boundary.

Feature ids are content digests (see
:func:`~sflkit.features.value.feature_id`), so the id of a feature is the same
in every process, and merging two trees is a structural union with observation
lists concatenated. The catalog kept beside the tree maps ids back to names, so
nothing is lost by recording ids.
"""

from collections import defaultdict
from typing import Dict, List, Optional

from sflkitlib.events.event import (
    FunctionEnterEvent,
    FunctionErrorEvent,
    FunctionExitEvent,
)

from sflkit.events.event_file import EventFile
from sflkit.features.handler import FeatureBuilder
from sflkit.features.value import FeatureValue

#: Name of the virtual node every run starts in.
ROOT = "ROOT"

#: Observations kept per run at each node: the first hit and a sliding last
#: hit. A hot loop would otherwise let one run dominate a node, while
#: observations from *different* runs are never evicted, which is what
#: discrimination between passing and failing runs needs.
DEFAULT_PER_RUN_CAP = 2


class TreeNode:
    """
    One function in the call tree, with the observations made at its boundaries.

    :ivar name: Canonical ``file:function:id`` identifier, or :data:`ROOT`.
    :ivar children: Child nodes keyed by name.
    :ivar enter: Observations recorded on entry, each ``{feature id: value}``.
    :ivar exit: Observations recorded on exit.
    """

    __slots__ = ("name", "children", "enter", "exit")

    def __init__(self, name: str):
        """
        :param name: Canonical function identifier.
        """
        self.name = name
        self.children: Dict[str, "TreeNode"] = dict()
        self.enter: List[Dict[int, int]] = list()
        self.exit: List[Dict[int, int]] = list()

    def child(self, name: str) -> "TreeNode":
        """
        :param name: Canonical identifier of the child.
        :returns: The child, created on first use.
        """
        node = self.children.get(name)
        if node is None:
            node = TreeNode(name)
            self.children[name] = node
        return node

    def merge(self, other: "TreeNode") -> None:
        """
        Fold *other* into this node, recursively.

        :param other: A node built elsewhere, for the same function.

        Merging is append-only: observations from different runs are all
        evidence and none of them replaces another. Only the structure is
        deduplicated.
        """
        self.enter.extend(other.enter)
        self.exit.extend(other.exit)
        for name, node in other.children.items():
            self.child(name).merge(node)

    def walk(self):
        """Yield every node in the subtree, this one first."""
        yield self
        for child in self.children.values():
            yield from child.walk()

    def __repr__(self):
        return f"TreeNode({self.name}, children={len(self.children)})"


class TreeBuilder(FeatureBuilder):
    """
    Builds feature vectors and a mergeable call tree from one event stream.

    A :class:`~sflkit.features.handler.FeatureBuilder` already sees every event
    (it registers itself among the analysis objects), so the tree costs one
    extra dispatch on function boundaries and nothing anywhere else.

    On entering a function a node is opened and the run's feature values are
    snapshotted; on leaving it they are snapshotted again and the node closes.
    That is what makes a node's observations comparable across runs: the same
    program point, the same feature ids, different values.

    :ivar root: The virtual root every run starts in.
    :ivar catalog: Feature id to feature name, for reading the tree back.
    :ivar per_run_cap: Observations kept per run at each node.
    """

    def __init__(self, per_run_cap: int = DEFAULT_PER_RUN_CAP):
        """
        :param per_run_cap: Observations to keep per run at each node. See
            :data:`DEFAULT_PER_RUN_CAP`.
        """
        super().__init__()
        self.root = TreeNode(ROOT)
        self.catalog: Dict[int, str] = dict()
        self.per_run_cap = per_run_cap
        # Per run, per thread: the open call stack. Threads interleave freely,
        # so a single stack would splice one thread's calls into another's.
        self._stacks: Dict[EventFile, Dict[Optional[int], List[TreeNode]]] = dict()
        self._counts: Dict[EventFile, Dict[str, int]] = dict()

    def prepare(self, event_file: EventFile, test_result) -> None:
        super().prepare(event_file, test_result)
        # A plain dict, not `defaultdict(lambda: [self.root])`: a lambda is not
        # picklable, and a builder that has prepared a run has to be able to
        # cross a process boundary for parallel building.
        self._stacks[event_file] = dict()
        self._counts[event_file] = defaultdict(int)

    @staticmethod
    def function_name(
        event: FunctionEnterEvent | FunctionExitEvent | FunctionErrorEvent,
    ) -> str:
        """
        :param event: Any function-boundary event.
        :returns: ``file:function:id``, which stays unique even when a file
            holds several functions of the same name.
        """
        return f"{event.file}:{event.function}:{event.function_id}"

    def hit(self, id_: EventFile, event, *args, **kwargs) -> None:
        """
        Record one event, then maintain the tree if it is a function boundary.

        :param id_: The run.
        :param event: The event.
        """
        super().hit(id_, event, *args, **kwargs)
        if isinstance(event, FunctionEnterEvent):
            stack = self._stack(id_, event.thread_id)
            node = stack[-1].child(self.function_name(event))
            stack.append(node)
            self._record(id_, node, node.enter)
        elif isinstance(event, (FunctionExitEvent, FunctionErrorEvent)):
            stack = self._stack(id_, event.thread_id)
            node = stack[-1]
            if node is not self.root:
                self._record(id_, node, node.exit)
                stack.pop()

    def _stack(self, id_: EventFile, thread_id: Optional[int]) -> List[TreeNode]:
        """
        Return the open call stack of one thread of a run.

        :param id_: The run.
        :param thread_id: The thread, or ``None`` when threads are not tracked.
        :returns: The stack, rooted at the tree's root on first use.
        """
        stacks = self._stacks[id_]
        stack = stacks.get(thread_id)
        if stack is None:
            stack = stacks[thread_id] = [self.root]
        return stack

    def _record(self, id_: EventFile, node: TreeNode, target: List[Dict[int, int]]):
        """
        Snapshot the run's current feature values into *target*.

        :param id_: The run.
        :param node: The node being observed.
        :param target: The node's entry or exit observation list.
        """
        key = f"{node.name}:{id(target)}"
        count = self._counts[id_][key]
        if count >= self.per_run_cap:
            # Keep the first observation and slide the last one.
            target.pop()
        else:
            self._counts[id_][key] = count + 1
        observation = dict()
        for feature, value in self.feature_vectors[id_].get_features().items():
            self.catalog[feature.id] = feature.name
            observation[feature.id] = value.value
        target.append(observation)

    def merge(self, other: "TreeBuilder") -> None:
        """
        Fold a builder that handled other runs into this one.

        Extends the vector merge with the tree: node structure is unioned and
        observations are concatenated, which is exactly what makes a tree built
        in pieces equal to one built in a single pass. Feature ids are content
        digests, so observations recorded in another process are directly
        comparable to these without translation.

        :param other: A builder that handled a different set of runs.
        """
        super().merge(other)
        self.catalog.update(other.catalog)
        self.root.merge(other.root)

    def post_process(self, event_file: EventFile) -> None:
        """
        Close the run by recording the root's exit observation.

        :param event_file: The finished run.
        """
        self._record(event_file, self.root, self.root.exit)

    def observations(self, node: TreeNode) -> List[Dict[str, FeatureValue]]:
        """
        Read a node's entry observations back as names and values.

        :param node: The node to read.
        :returns: One dict per observation.
        """
        return [
            {
                self.catalog[fid]: FeatureValue(value)
                for fid, value in observation.items()
            }
            for observation in node.enter
        ]
