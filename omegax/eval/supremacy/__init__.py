"""Benchmark Dominance & Frontier Tracking Framework.

Runs the system against benchmark suites, scalarizes results through a
configurable objective that prizes generalization and out-of-distribution
resilience, and enforces a zero-tolerance regression shield that rolls back any
update failing to surpass its baseline.
"""

from omegax.eval.supremacy.benchmark import (
    BenchmarkResult,
    BenchmarkSuite,
    BenchmarkTask,
    Harvester,
)
from omegax.eval.supremacy.objective import ObjectiveWeights, SupremacyObjective
from omegax.eval.supremacy.regression import RegressionShield, RegressionVerdict

__all__ = [
    "BenchmarkResult",
    "BenchmarkSuite",
    "BenchmarkTask",
    "Harvester",
    "ObjectiveWeights",
    "SupremacyObjective",
    "RegressionShield",
    "RegressionVerdict",
]
