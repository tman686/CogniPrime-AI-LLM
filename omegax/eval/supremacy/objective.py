"""Competitive Supremacy objective function.

Scalarizes a :class:`~omegax.eval.supremacy.benchmark.BenchmarkResult` into a
single objective the matrix maximizes. The default weighting prioritizes
out-of-distribution resilience and generalization over raw in-distribution
accuracy, per the "zero-shot generalization and OOD resilience" objective.
"""

from __future__ import annotations

from dataclasses import dataclass

from omegax.eval.supremacy.benchmark import BenchmarkResult


@dataclass(slots=True, frozen=True)
class ObjectiveWeights:
    """Weights over benchmark metrics. Should sum to ~1 for interpretability."""

    accuracy: float = 0.3
    ood: float = 0.5
    efficiency: float = 0.2


class SupremacyObjective:
    """Combines benchmark metrics into a single maximization objective."""

    def __init__(self, weights: ObjectiveWeights | None = None) -> None:
        self.weights = weights or ObjectiveWeights()

    def score(self, result: BenchmarkResult, *, efficiency: float = 0.0) -> float:
        """Scalarize a benchmark result.

        ``efficiency`` (0-1, higher is better — e.g. derived from latency/cost)
        is supplied separately since it comes from telemetry, not the suite.
        """
        w = self.weights
        return (
            w.accuracy * result.score("accuracy")
            + w.ood * result.score("ood")
            + w.efficiency * efficiency
        )
