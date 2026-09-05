"""Zero-Tolerance Regression Shield.

Guards every promotion: an updated module must *decisively* surpass the prior
baseline objective. If it fails to, the shield's verdict is to roll back. This
is the one piece of automation that is intentionally *not* gated — rolling back
to a known-good baseline is always safe and always the right move on a
regression.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class RegressionVerdict(str, enum.Enum):
    """Outcome of comparing a candidate objective to the baseline."""

    IMPROVED = "improved"  # decisively better — keep
    NEUTRAL = "neutral"  # within the margin — keep baseline, no rollback needed
    REGRESSED = "regressed"  # worse — roll back


@dataclass(slots=True)
class RegressionShield:
    """Compares candidate objectives against a moving baseline.

    Attributes:
        baseline: The current best objective value.
        margin: Minimum improvement over baseline to count as ``IMPROVED``.
    """

    baseline: float = 0.0
    margin: float = 1e-6

    def evaluate(self, candidate: float) -> RegressionVerdict:
        """Return the verdict for a candidate objective value."""
        if candidate < self.baseline - self.margin:
            return RegressionVerdict.REGRESSED
        if candidate > self.baseline + self.margin:
            return RegressionVerdict.IMPROVED
        return RegressionVerdict.NEUTRAL

    def accept(self, candidate: float) -> bool:
        """Evaluate a candidate and, if it improved, advance the baseline.

        Returns True when the candidate was kept (improved or neutral), False
        when it regressed and should be rolled back.
        """
        verdict = self.evaluate(candidate)
        if verdict is RegressionVerdict.REGRESSED:
            return False
        if verdict is RegressionVerdict.IMPROVED:
            self.baseline = candidate
        return True
