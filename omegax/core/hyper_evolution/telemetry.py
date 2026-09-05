"""Hyper-Telemetry & latency profiling.

The profiler is the meta-monitoring layer: it captures per-region execution
traces (wall time, call counts, and optional custom metrics) and aggregates
them into a :class:`TelemetryReport` that ranks the hot paths the evolution
core should target. It is real, deterministic, and dependency-free — a context
manager wrapping timed regions.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(slots=True)
class Trace:
    """Aggregated timing for a single named region."""

    region: str
    calls: int = 0
    total_ns: int = 0
    max_ns: int = 0
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def mean_ns(self) -> float:
        return self.total_ns / self.calls if self.calls else 0.0


@dataclass(slots=True, frozen=True)
class HotPath:
    """A region flagged as a bottleneck, with its share of total time."""

    region: str
    total_ns: int
    calls: int
    share: float  # fraction of total profiled time


@dataclass(slots=True)
class TelemetryReport:
    """A snapshot of profiled regions ranked by total time spent."""

    traces: list[Trace] = field(default_factory=list)

    @property
    def total_ns(self) -> int:
        return sum(t.total_ns for t in self.traces)

    def hot_paths(self, *, top_k: int = 5, min_share: float = 0.0) -> list[HotPath]:
        """Return the ``top_k`` regions by total time, above ``min_share``."""
        total = self.total_ns or 1
        ranked = sorted(self.traces, key=lambda t: t.total_ns, reverse=True)
        paths = [
            HotPath(
                region=t.region,
                total_ns=t.total_ns,
                calls=t.calls,
                share=t.total_ns / total,
            )
            for t in ranked
        ]
        return [p for p in paths if p.share >= min_share][:top_k]


class TelemetryProfiler:
    """Collects timed traces across runtime regions.

    Usage::

        profiler = TelemetryProfiler()
        with profiler.region("attention"):
            ...
        report = profiler.report()
        hot = report.hot_paths()
    """

    def __init__(self, *, clock=time.perf_counter_ns) -> None:
        self._clock = clock
        self._traces: dict[str, Trace] = {}

    @contextmanager
    def region(self, name: str, **metrics: float) -> Iterator[None]:
        """Time a code region, optionally attaching custom metrics."""
        start = self._clock()
        try:
            yield
        finally:
            elapsed = self._clock() - start
            self.record(name, elapsed, **metrics)

    def record(self, region: str, elapsed_ns: int, **metrics: float) -> None:
        """Record a single timed sample for ``region``."""
        trace = self._traces.get(region)
        if trace is None:
            trace = Trace(region=region)
            self._traces[region] = trace
        trace.calls += 1
        trace.total_ns += int(elapsed_ns)
        trace.max_ns = max(trace.max_ns, int(elapsed_ns))
        for key, value in metrics.items():
            trace.metrics[key] = trace.metrics.get(key, 0.0) + value

    def report(self) -> TelemetryReport:
        """Return an immutable snapshot of the collected traces."""
        return TelemetryReport(traces=list(self._traces.values()))

    def reset(self) -> None:
        self._traces.clear()
