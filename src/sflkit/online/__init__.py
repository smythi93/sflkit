"""
Building analysis artifacts while the program under test runs.

The offline workflow stays as it is: instrument, execute, write a trace, read
it back. This package adds a second one that skips the trace entirely. A
tracer materializes the same events from CPython's monitoring hooks and the
static event mapping, and listeners turn them into spectra, feature vectors and
a call tree as they arrive.

What it buys: no trace on disk and none in memory, no second pass over the
events, and a run that executes the program as shipped rather than an
instrumented copy of it. What it costs: slower execution, since every observed
location goes through a Python callback, and two event types that cannot be
recovered from outside the program (see :mod:`sflkit.online.tracer`).
"""

from sflkit.online.listener import (
    BuilderListener,
    EventListener,
    ListenerGroup,
    ModelListener,
    OnlineError,
    SpectrumListener,
    spectrum_factory,
)
from sflkit.online.session import OnlineSession, RunArtifact, Suite, trace
from sflkit.online.tracer import (
    LocationIndex,
    MonitoringTracer,
    SUPPORTED_EVENT_TYPES,
    SysTraceTracer,
    Tracer,
    get_tracer,
)
from sflkit.online.tree import TreeBuilder, TreeNode

__all__ = [
    "BuilderListener",
    "EventListener",
    "ListenerGroup",
    "LocationIndex",
    "ModelListener",
    "MonitoringTracer",
    "OnlineError",
    "OnlineSession",
    "RunArtifact",
    "SUPPORTED_EVENT_TYPES",
    "SpectrumListener",
    "Suite",
    "SysTraceTracer",
    "Tracer",
    "TreeBuilder",
    "TreeNode",
    "get_tracer",
    "spectrum_factory",
    "trace",
]
