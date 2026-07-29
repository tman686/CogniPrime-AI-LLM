"""Atomic staging & rollback pipeline.

A :class:`StagingPipeline` guards the transition from a self-generated
:class:`Candidate` to committed state. Each promotion:

1. snapshots the current committed state,
2. verifies the candidate in a :class:`~omegax.sandbox.runner.SandboxRunner`,
3. on success, atomically commits and records the new state,
4. on failure (or on a later regression), rolls back to the snapshot.

The pipeline holds an opaque ``state`` object (whatever the caller is
evolving — a config dict, a module registry, a metric baseline). It never
mutates state except through :meth:`promote` / :meth:`rollback`.
"""

from __future__ import annotations

import copy
import enum
from dataclasses import dataclass
from typing import Any

from omegax.sandbox.runner import SandboxReport, SandboxRunner


class StageOutcome(str, enum.Enum):
    """Result of attempting to promote a candidate."""

    COMMITTED = "committed"
    REJECTED = "rejected"  # failed verification
    BLOCKED = "blocked"  # verification passed but approval withheld


@dataclass(slots=True, frozen=True)
class Candidate:
    """A self-generated change awaiting promotion."""

    candidate_id: str
    description: str
    code: str
    # The state this candidate would install if committed.
    next_state: Any


@dataclass(slots=True, frozen=True)
class Snapshot:
    """A point-in-time copy of committed state, used for rollback."""

    snapshot_id: str
    state: Any


@dataclass(slots=True)
class ValidationResult:
    """A candidate paired with its sandbox verification report."""

    candidate: Candidate
    report: SandboxReport
    outcome: StageOutcome
    snapshot: Snapshot | None = None


class StagingPipeline:
    """Atomic promote/rollback around a sandbox-verified candidate."""

    def __init__(self, initial_state: Any, runner: SandboxRunner) -> None:
        self._state = initial_state
        self._runner = runner
        self._snapshots: list[Snapshot] = []
        self._counter = 0

    @property
    def state(self) -> Any:
        return self._state

    def snapshot(self) -> Snapshot:
        """Capture the current committed state for later rollback."""
        self._counter += 1
        snap = Snapshot(snapshot_id=f"snap-{self._counter}", state=copy.deepcopy(self._state))
        self._snapshots.append(snap)
        return snap

    def promote(self, candidate: Candidate, *, approved: bool = True) -> ValidationResult:
        """Verify and, if approved, atomically commit a candidate.

        ``approved`` reflects an upstream :class:`~cogniprime.approval.ApprovalGate`
        decision. A candidate that passes verification but is not approved is
        returned with :attr:`StageOutcome.BLOCKED` and no state change.
        """
        snap = self.snapshot()
        report = self._runner.verify(candidate.code)
        if not report.passed:
            return ValidationResult(candidate, report, StageOutcome.REJECTED, snap)
        if not approved:
            return ValidationResult(candidate, report, StageOutcome.BLOCKED, snap)
        # Atomic commit: state is replaced only after verification + approval.
        self._state = candidate.next_state
        return ValidationResult(candidate, report, StageOutcome.COMMITTED, snap)

    def rollback(self, snapshot: Snapshot) -> None:
        """Restore committed state from a snapshot (always safe, never gated)."""
        self._state = copy.deepcopy(snapshot.state)

    @property
    def snapshots(self) -> list[Snapshot]:
        return list(self._snapshots)
