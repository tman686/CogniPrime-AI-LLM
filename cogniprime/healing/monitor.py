"""Production monitoring for the Self-Healing Compiler.

The monitor is the source of truth for *what code exists* and *which units look
unhealthy*. It emits :class:`HealthSignal` objects — the triage queue the
diagnostician works through. Health can come from static heuristics (as in the
bundled :class:`HeuristicMonitor`) or from live telemetry (error rates, crash
loops) via a custom :class:`ProductionMonitor` implementation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Protocol


@dataclass(slots=True, frozen=True)
class CodeUnit:
    """A single monitored unit of production code (a file or module)."""

    unit_id: str
    path: str
    source: str
    holding: str  # which company/holding owns this code


@dataclass(slots=True, frozen=True)
class HealthSignal:
    """An indication that a code unit may need attention.

    ``severity_hint`` is a cheap 0-1 pre-score from the monitor; the
    diagnostician produces the authoritative severity.
    """

    unit: CodeUnit
    reason: str
    severity_hint: float


class ProductionMonitor(Protocol):
    """Surfaces code units that warrant a diagnostic pass."""

    def units(self) -> Iterable[CodeUnit]:
        """Yield every monitored code unit."""
        ...

    def scan(self) -> list[HealthSignal]:
        """Return health signals for units that look unhealthy."""
        ...


# Cheap static smells used by the bundled heuristic monitor. Each maps a
# regex to a short reason and a severity hint.
_SMELLS: tuple[tuple[re.Pattern[str], str, float], ...] = (
    (re.compile(r"\beval\s*\("), "use of eval() — code-injection risk", 0.9),
    (re.compile(r"\bexec\s*\("), "use of exec() — code-injection risk", 0.9),
    (re.compile(r"except\s*:\s*(#|$|\n)"), "bare except — swallows errors", 0.5),
    (re.compile(r"verify\s*=\s*False"), "TLS verification disabled", 0.8),
    (re.compile(r"#\s*TODO|#\s*FIXME"), "unresolved TODO/FIXME in production", 0.3),
    (re.compile(r"password\s*=\s*[\"']"), "hard-coded credential", 0.95),
)


@dataclass(slots=True)
class HeuristicMonitor:
    """A dependency-free :class:`ProductionMonitor` using static code smells.

    Real deployments back the monitor with runtime telemetry; this heuristic
    version lets the healing pipeline run and be tested without live systems.
    """

    _units: list[CodeUnit] = field(default_factory=list)

    def register(self, unit: CodeUnit) -> None:
        self._units.append(unit)

    def units(self) -> Iterable[CodeUnit]:
        return list(self._units)

    def scan(self) -> list[HealthSignal]:
        signals: list[HealthSignal] = []
        for unit in self._units:
            best: tuple[str, float] | None = None
            for pattern, reason, hint in _SMELLS:
                if pattern.search(unit.source):
                    if best is None or hint > best[1]:
                        best = (reason, hint)
            if best is not None:
                signals.append(
                    HealthSignal(unit=unit, reason=best[0], severity_hint=best[1])
                )
        signals.sort(key=lambda s: s.severity_hint, reverse=True)
        return signals
