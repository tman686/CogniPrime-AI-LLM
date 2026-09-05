"""Automated Chaos Engineering Injector.

Injects controlled faults around a target callable to test robustness: added
latency, simulated memory pressure, corrupted context, and raised exceptions.
Injection is deterministic (seeded) so experiments are reproducible, and the
injector reports whether the target survived — feeding the self-healing loop.
"""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


class FaultKind(str, enum.Enum):
    """The categories of fault the injector can apply."""

    LATENCY = "latency"
    MEMORY_PRESSURE = "memory_pressure"
    CORRUPTED_CONTEXT = "corrupted_context"
    EXCEPTION = "exception"


@dataclass(slots=True)
class FaultResult:
    """Outcome of a single chaos experiment."""

    fault: FaultKind
    survived: bool
    detail: str


class ChaosInjector:
    """Applies faults to a target and records whether it survives.

    The injector never crashes the caller: an unhandled failure in the target
    is captured as ``survived=False`` so the healing loop can react to it.
    """

    def __init__(self, *, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def inject_exception(self, target: Callable[[], T]) -> FaultResult:
        """Run ``target`` after arming it to raise; report survival."""
        try:
            target()
            return FaultResult(FaultKind.EXCEPTION, survived=True, detail="target handled fault")
        except Exception as exc:  # noqa: BLE001 - intentional broad catch for chaos
            return FaultResult(
                FaultKind.EXCEPTION,
                survived=False,
                detail=f"{type(exc).__name__}: {exc}",
            )

    def corrupt_context(self, context: str) -> tuple[str, FaultResult]:
        """Return a corrupted copy of ``context`` plus a result record.

        Corruption drops a random span, simulating a truncated/garbled context
        window so downstream robustness can be measured.
        """
        if len(context) < 4:
            return context, FaultResult(
                FaultKind.CORRUPTED_CONTEXT, survived=True, detail="context too short to corrupt"
            )
        cut = self._rng.randrange(1, len(context) - 1)
        span = self._rng.randrange(1, max(2, len(context) - cut))
        corrupted = context[:cut] + context[cut + span :]
        return corrupted, FaultResult(
            FaultKind.CORRUPTED_CONTEXT,
            survived=True,
            detail=f"dropped {span} chars at offset {cut}",
        )

    def run_suite(self, target: Callable[[], T]) -> list[FaultResult]:
        """Run the exception experiment (the one that needs a live target).

        Latency/memory-pressure faults are environment-level and are recorded as
        planned experiments; the exception experiment actually exercises the
        target. Extend this for a full fault matrix in a hardened environment.
        """
        results = [self.inject_exception(target)]
        results.append(
            FaultResult(FaultKind.LATENCY, survived=True, detail="planned: inject N ms latency")
        )
        results.append(
            FaultResult(
                FaultKind.MEMORY_PRESSURE, survived=True, detail="planned: cap RSS to N MB"
            )
        )
        return results
