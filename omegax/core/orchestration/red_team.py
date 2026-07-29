"""Autonomous adversarial red-team arbitrator.

Before a self-generated change is deployed, an adversarial team attacks it: a
set of :class:`AdversarialProbe`s attempt to break the candidate in a sandbox.
If any *critical* probe fails, the arbitrator returns :class:`Verdict.BLOCK`,
stops deployment, and emits the failing probes as high-priority findings that
feed back into the evolution engine as training targets.

This is a deployment gate, not a background attacker with side effects — it runs
candidates through the same sandbox runner the rest of Omega-X uses.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable

from omegax.sandbox.runner import SandboxRunner

# A probe builds a runnable program from the candidate code; the sandbox decides
# pass/fail. Return the program string to execute against the candidate.
ProbeBuilder = Callable[[str], str]


class Verdict(str, enum.Enum):
    """The arbitrator's deployment decision."""

    APPROVE = "approve"
    BLOCK = "block"


@dataclass(slots=True, frozen=True)
class AdversarialProbe:
    """A single adversarial test against a candidate."""

    name: str
    build: ProbeBuilder
    critical: bool = True


@dataclass(slots=True, frozen=True)
class Finding:
    """A probe failure, promotable to a high-priority training item."""

    probe: str
    critical: bool
    detail: str


@dataclass(slots=True)
class ArbitrationResult:
    """The outcome of arbitrating one candidate."""

    verdict: Verdict
    findings: list[Finding] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return self.verdict is Verdict.APPROVE

    def training_items(self) -> list[str]:
        """Render findings as high-priority training prompts for the evolver."""
        return [
            f"Harden against: {f.probe} — {f.detail}"
            for f in self.findings
            if f.critical
        ]


class RedTeamArbitrator:
    """Runs adversarial probes and blocks deployment on critical failure."""

    def __init__(self, runner: SandboxRunner, probes: list[AdversarialProbe] | None = None) -> None:
        self.runner = runner
        self.probes = probes or []

    def add_probe(self, probe: AdversarialProbe) -> None:
        self.probes.append(probe)

    def arbitrate(self, candidate_code: str) -> ArbitrationResult:
        """Attack the candidate; block if any critical probe fails."""
        result = ArbitrationResult(verdict=Verdict.APPROVE)
        for probe in self.probes:
            report = self.runner.verify(probe.build(candidate_code))
            if not report.passed:
                result.findings.append(
                    Finding(probe=probe.name, critical=probe.critical, detail=report.detail)
                )
        if any(f.critical for f in result.findings):
            result.verdict = Verdict.BLOCK
        return result
