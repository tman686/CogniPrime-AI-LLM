"""Tests for the Benchmark Dominance & Frontier Tracking framework."""

from __future__ import annotations

from omegax.eval.supremacy.benchmark import BenchmarkSuite, BenchmarkTask, Harvester
from omegax.eval.supremacy.objective import ObjectiveWeights, SupremacyObjective
from omegax.eval.supremacy.regression import RegressionShield, RegressionVerdict


def _suite() -> BenchmarkSuite:
    return BenchmarkSuite(
        name="reasoning",
        tasks=[
            BenchmarkTask("t1", "2+2", "4"),
            BenchmarkTask("t2", "cap of France", "Paris"),
            BenchmarkTask("t3", "ood item", "42", ood=True),
        ],
    )


def _system(answers: dict[str, str]):
    return lambda prompt: answers.get(prompt, "")


def test_harvester_computes_accuracy_and_ood() -> None:
    suite = _suite()
    system = _system({"2+2": "4", "cap of France": "Paris", "ood item": "wrong"})
    result = Harvester().run(suite, system)
    assert result.score("accuracy") == 2 / 3
    assert result.score("ood") == 0.0  # the one OOD task was wrong


def test_supremacy_objective_weights_ood_heaviest() -> None:
    suite = _suite()
    # Solve everything, including OOD.
    system = _system({"2+2": "4", "cap of France": "Paris", "ood item": "42"})
    result = Harvester().run(suite, system)
    obj = SupremacyObjective(ObjectiveWeights(accuracy=0.3, ood=0.5, efficiency=0.2))
    score = obj.score(result, efficiency=1.0)
    # accuracy=1, ood=1, efficiency=1 -> weighted sum = 1.0
    assert abs(score - 1.0) < 1e-9


def test_regression_shield_verdicts() -> None:
    shield = RegressionShield(baseline=0.5)
    assert shield.evaluate(0.6) is RegressionVerdict.IMPROVED
    assert shield.evaluate(0.4) is RegressionVerdict.REGRESSED
    assert shield.evaluate(0.5) is RegressionVerdict.NEUTRAL


def test_regression_shield_accept_advances_baseline_only_on_improvement() -> None:
    shield = RegressionShield(baseline=0.5)
    assert shield.accept(0.7) is True
    assert shield.baseline == 0.7
    # A regression is rejected and does not move the baseline.
    assert shield.accept(0.6) is False
    assert shield.baseline == 0.7
