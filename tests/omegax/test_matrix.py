"""Integration tests for the Omega-X matrix loop and self-healing recovery."""

from __future__ import annotations

import json
from typing import Any

from cogniprime.approval import AutoApproveGate, AutoDenyGate
from cogniprime.llm import LLMClient
from omegax.config import OmegaConfig
from omegax.core.hyper_evolution.telemetry import HotPath
from omegax.eval.supremacy.benchmark import BenchmarkSuite, BenchmarkTask
from omegax.matrix import OmegaMatrix
from omegax.sandbox.runner import InProcessValidator
from omegax.sandbox.staging import StageOutcome
from tests.fakes import FakeSDK


def _responder(kwargs: dict[str, Any]) -> str:
    fmt = kwargs.get("output_config", {}).get("format")
    if fmt is None:
        return "solution text"
    props = set(fmt["schema"]["properties"])
    if "rewritten_source" in props:
        return json.dumps(
            {
                "rewritten_source": "def f():\n    return 42  # optimized\n",
                "optimization": "constant fold",
                "expected_speedup": 2.0,
                "preserves_behavior": True,
                "changed": True,
            }
        )
    if "checker_code" in props:
        return json.dumps(
            {
                "domain": "math",
                "prompt": "compute",
                "reference_solution": "42",
                "verifiable": True,
                "checker_code": "assert True\n",
            }
        )
    if "self_test" in props:
        return json.dumps(
            {
                "name": "slugify",
                "description": "make a slug",
                "code": "def slugify(s): return s.lower()",
                "self_test": "assert True\n",
            }
        )
    if "escalate" in props:
        return json.dumps({"solved": True, "escalate": False, "notes": "ok"})
    if "root_cause" in props:
        return json.dumps(
            {
                "root_cause": "unhandled None",
                "patched_source": "def f():\n    return 0\n",
                "confidence": 0.9,
                "changed": True,
            }
        )
    raise AssertionError(f"unexpected schema: {props}")


def _matrix(approval) -> OmegaMatrix:
    config = OmegaConfig(api_key="test")
    llm = LLMClient(config.to_cogniprime(), sdk_client=FakeSDK(_responder))
    return OmegaMatrix(
        config,
        llm=llm,
        approval=approval,
        runner=InProcessValidator(lambda _c: (True, "ok")),
        source_map={"f": "def f():\n    return 6 * 7\n"},
    )


def _suite() -> BenchmarkSuite:
    return BenchmarkSuite("s", tasks=[BenchmarkTask("t", "q", "a")])


def test_evolve_blocked_without_approval() -> None:
    matrix = _matrix(AutoDenyGate())
    result = matrix.evolve(HotPath("f", 9000, 3, 0.9))
    assert result.proposal is not None  # rewrite still generated
    assert result.outcome is StageOutcome.BLOCKED
    assert result.committed is False
    assert matrix.staging.state["f"] == "def f():\n    return 6 * 7\n"  # unchanged


def test_evolve_commits_with_approval() -> None:
    matrix = _matrix(AutoApproveGate())
    result = matrix.evolve(HotPath("f", 9000, 3, 0.9))
    assert result.committed is True
    assert "optimized" in matrix.staging.state["f"]


def test_full_step_records_ledger_and_synthesizes() -> None:
    matrix = _matrix(AutoApproveGate())

    def system(prompt: str) -> str:  # solves the suite
        return "a"

    report = matrix.step(
        [HotPath("f", 9000, 3, 0.9)],
        suite=_suite(),
        system=system,
        efficiency=1.0,
        synthesize_domain="math",
    )
    assert report.evolutions[0].committed is True
    assert report.evaluation is not None
    assert report.trajectories_remembered == 1
    assert report.ledger_verified is True
    # The ledger recorded the whole cycle and stayed internally consistent.
    assert matrix.ledger.verify()
    events = [e.event for e in matrix.ledger.entries]
    assert "cycle.start" in events and "cycle.end" in events


def test_regression_triggers_auto_rollback() -> None:
    matrix = _matrix(AutoApproveGate())
    # Commit a change first.
    matrix.evolve(HotPath("f", 9000, 3, 0.9))
    assert "optimized" in matrix.staging.state["f"]

    # Force the shield baseline high so the next eval regresses.
    matrix.shield.baseline = 0.99

    def system(prompt: str) -> str:  # scores 0 -> regression
        return "wrong"

    evaluation = matrix.evaluate(_suite(), system, efficiency=0.0)
    assert evaluation.rolled_back is True
    # Rolled back to the pre-commit snapshot captured during promote.
    assert matrix.staging.state["f"] == "def f():\n    return 6 * 7\n"


def test_capability_registration_is_gated() -> None:
    denied = _matrix(AutoDenyGate())
    assert denied.synthesize_capability("need a slugify helper") is False
    assert len(denied.registry) == 0

    approved = _matrix(AutoApproveGate())
    assert approved.synthesize_capability("need a slugify helper") is True
    assert len(approved.registry) == 1


def test_heal_stages_gated_fix() -> None:
    matrix = _matrix(AutoDenyGate())  # gate on -> deny
    outcome = matrix.heal("Traceback ... TypeError", region="f")
    assert outcome is not None
    assert outcome.outcome is StageOutcome.BLOCKED  # proposed but not applied
    assert matrix.staging.state["f"] == "def f():\n    return 6 * 7\n"
