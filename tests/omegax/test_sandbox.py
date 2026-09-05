"""Tests for the sandbox: staging pipeline and runners."""

from __future__ import annotations

from omegax.sandbox.runner import InProcessValidator, SubprocessSandbox
from omegax.sandbox.staging import Candidate, StageOutcome, StagingPipeline


def _always_pass() -> InProcessValidator:
    return InProcessValidator(lambda _c: (True, "ok"))


def _always_fail() -> InProcessValidator:
    return InProcessValidator(lambda _c: (False, "nope"))


def test_promote_commits_on_pass_and_approval() -> None:
    pipe = StagingPipeline({"v": 1}, _always_pass())
    cand = Candidate("c1", "bump", code="print(1)", next_state={"v": 2})
    result = pipe.promote(cand, approved=True)
    assert result.outcome is StageOutcome.COMMITTED
    assert pipe.state == {"v": 2}


def test_promote_blocked_without_approval_leaves_state() -> None:
    pipe = StagingPipeline({"v": 1}, _always_pass())
    cand = Candidate("c1", "bump", code="print(1)", next_state={"v": 2})
    result = pipe.promote(cand, approved=False)
    assert result.outcome is StageOutcome.BLOCKED
    assert pipe.state == {"v": 1}  # unchanged


def test_promote_rejected_on_failed_verification() -> None:
    pipe = StagingPipeline({"v": 1}, _always_fail())
    cand = Candidate("c1", "bad", code="raise SystemExit(1)", next_state={"v": 2})
    result = pipe.promote(cand, approved=True)
    assert result.outcome is StageOutcome.REJECTED
    assert pipe.state == {"v": 1}


def test_rollback_restores_snapshot() -> None:
    pipe = StagingPipeline({"v": 1}, _always_pass())
    snap = pipe.snapshot()
    pipe.promote(Candidate("c", "d", "print(1)", next_state={"v": 99}), approved=True)
    assert pipe.state == {"v": 99}
    pipe.rollback(snap)
    assert pipe.state == {"v": 1}


def test_subprocess_sandbox_runs_safe_snippet() -> None:
    sandbox = SubprocessSandbox(timeout_seconds=10.0)
    report = sandbox.verify("assert 2 + 2 == 4\n")
    assert report.passed
    assert not report.timed_out


def test_subprocess_sandbox_flags_failure() -> None:
    sandbox = SubprocessSandbox(timeout_seconds=10.0)
    report = sandbox.verify("raise SystemExit(3)\n")
    assert not report.passed
