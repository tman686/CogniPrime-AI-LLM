"""Bounded parallel sub-agent swarm.

Breaks a large job into many sub-tasks and runs them concurrently with a hard
worker cap. "Hundreds of sub-agents" in principle, but always bounded — an
unbounded thread/agent explosion is a reliability and cost hazard, not a
feature. Each task's success or failure is captured individually so one failing
sub-agent never sinks the batch.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from typing import Callable, Generic, TypeVar

R = TypeVar("R")

# Absolute ceiling on concurrent workers regardless of requested size.
MAX_WORKERS_CAP = 64


@dataclass(slots=True)
class SwarmTask(Generic[R]):
    """One unit of work for the swarm."""

    task_id: str
    run: Callable[[], R]


@dataclass(slots=True)
class SwarmResult(Generic[R]):
    """Per-task outcomes from a swarm execution."""

    results: dict[str, R] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def completed(self) -> int:
        return len(self.results)


class SubAgentSwarm:
    """Runs many sub-tasks concurrently under a bounded worker pool."""

    def __init__(self, *, max_workers: int = 16) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self.max_workers = min(max_workers, MAX_WORKERS_CAP)

    def run(self, tasks: list[SwarmTask[R]]) -> SwarmResult[R]:
        """Execute all tasks concurrently, isolating per-task failures."""
        result: SwarmResult[R] = SwarmResult()
        if not tasks:
            return result

        workers = min(self.max_workers, len(tasks))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_id = {pool.submit(task.run): task.task_id for task in tasks}
            for future in concurrent.futures.as_completed(future_to_id):
                task_id = future_to_id[future]
                try:
                    result.results[task_id] = future.result()
                except Exception as exc:  # noqa: BLE001 - isolate sub-agent failures
                    result.errors[task_id] = f"{type(exc).__name__}: {exc}"
        return result
