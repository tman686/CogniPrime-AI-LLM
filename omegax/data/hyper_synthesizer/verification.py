"""Automated Formal Verification Harvester.

Synthetic outputs are only kept as training data if they *pass* mechanical
verification. The harvester runs each candidate's checker in a sandbox and
retains only verified samples — the absolute-truth-validation filter that keeps
the synthetic corpus from drifting into plausible-but-wrong data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from omegax.data.hyper_synthesizer.curriculum import Challenge
from omegax.sandbox.runner import SandboxReport, SandboxRunner


@dataclass(slots=True, frozen=True)
class VerifiedSample:
    """A challenge/solution pair that passed mechanical verification."""

    challenge: Challenge
    solution: str
    report: SandboxReport


@dataclass(slots=True)
class VerificationHarvester:
    """Filters synthetic samples down to those a checker verifies.

    A candidate is verified by composing the challenge's ``checker_code`` with
    the submitted solution and running it in the sandbox. Non-verifiable
    challenges (no checker) are dropped rather than trusted.
    """

    runner: SandboxRunner
    kept: list[VerifiedSample] = field(default_factory=list)
    rejected: int = 0

    def harvest(self, challenge: Challenge, solution: str) -> VerifiedSample | None:
        """Verify one solution; retain and return it only if it passes."""
        if not challenge.verifiable or not challenge.checker_code.strip():
            self.rejected += 1
            return None

        program = self._compose(challenge.checker_code, solution)
        report = self.runner.verify(program)
        if not report.passed:
            self.rejected += 1
            return None

        sample = VerifiedSample(challenge=challenge, solution=solution, report=report)
        self.kept.append(sample)
        return sample

    @staticmethod
    def _compose(checker_code: str, solution: str) -> str:
        """Build a runnable program that binds ``solution`` then runs the checker."""
        literal = repr(solution)
        return f"solution = {literal}\n{checker_code}\n"

    @property
    def yield_rate(self) -> float:
        """Fraction of attempted samples that were verified and kept."""
        total = len(self.kept) + self.rejected
        return len(self.kept) / total if total else 0.0
