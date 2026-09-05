"""Benchmark harvester and suite runner.

A :class:`BenchmarkSuite` is a set of :class:`BenchmarkTask`s, each with a
grader. The :class:`Harvester` runs a candidate system (any callable mapping a
prompt to an answer) over the suite and reports per-metric scores. Metrics are
kept general (``accuracy``, ``ood`` for out-of-distribution tasks, ``efficiency``)
so the objective function can weight them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# A system under test: prompt -> answer.
SystemFn = Callable[[str], str]
# A grader: (answer, task) -> score in [0, 1].
Grader = Callable[[str, "BenchmarkTask"], float]


@dataclass(slots=True, frozen=True)
class BenchmarkTask:
    """A single benchmark item."""

    task_id: str
    prompt: str
    expected: str
    ood: bool = False  # out-of-distribution item
    weight: float = 1.0


@dataclass(slots=True)
class BenchmarkSuite:
    """A named collection of benchmark tasks with a shared grader."""

    name: str
    tasks: list[BenchmarkTask] = field(default_factory=list)
    grader: Grader | None = None

    def default_grader(self, answer: str, task: BenchmarkTask) -> float:
        """Exact-match grader used when no custom grader is supplied."""
        return 1.0 if answer.strip() == task.expected.strip() else 0.0


@dataclass(slots=True)
class BenchmarkResult:
    """Aggregated scores for one run of a suite."""

    suite: str
    metrics: dict[str, float] = field(default_factory=dict)
    per_task: dict[str, float] = field(default_factory=dict)

    def score(self, metric: str, default: float = 0.0) -> float:
        return self.metrics.get(metric, default)


class Harvester:
    """Runs a system over a benchmark suite and aggregates metrics."""

    def run(self, suite: BenchmarkSuite, system: SystemFn) -> BenchmarkResult:
        grader = suite.grader or suite.default_grader
        result = BenchmarkResult(suite=suite.name)

        total_w = 0.0
        acc_num = 0.0
        ood_w = 0.0
        ood_num = 0.0
        for task in suite.tasks:
            answer = system(task.prompt)
            score = grader(answer, task)
            result.per_task[task.task_id] = score
            total_w += task.weight
            acc_num += score * task.weight
            if task.ood:
                ood_w += task.weight
                ood_num += score * task.weight

        result.metrics["accuracy"] = acc_num / total_w if total_w else 0.0
        result.metrics["ood"] = ood_num / ood_w if ood_w else result.metrics["accuracy"]
        return result
