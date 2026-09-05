"""Tests for the Snap-Off Engine: opportunity -> scaffold -> gated launch."""

from __future__ import annotations

import json
from typing import Any

from cogniprime.approval import AutoApproveGate, AutoDenyGate
from cogniprime.config import CogniPrimeConfig
from cogniprime.core.context_core import ContextCore
from cogniprime.core.data_layers import Document, LayerKind, StaticLayer
from cogniprime.llm import LLMClient
from cogniprime.snapoff.engine import SnapOffEngine
from tests.fakes import FakeSDK


def _responder(kwargs: dict[str, Any]) -> str:
    fmt = kwargs.get("output_config", {}).get("format")
    if fmt is None:
        return "Free-text analysis of the ecosystem."
    props = set(fmt["schema"]["properties"])
    if "follow_up_queries" in props:  # context expansion planning
        return json.dumps({"sufficient": True, "follow_up_queries": []})
    if "opportunities" in props:  # opportunity extraction
        return json.dumps(
            {
                "opportunities": [
                    {
                        "title": "Payments spin-off",
                        "rationale": "High checkout failure rate signals demand.",
                        "kind": "market",
                        "impact_score": 80.0,
                        "confidence": 0.7,
                    },
                    {
                        "title": "Minor tooling",
                        "rationale": "Small internal gap.",
                        "kind": "bottleneck",
                        "impact_score": 20.0,
                        "confidence": 0.5,
                    },
                ]
            }
        )
    if "service_name" in props:  # repo scaffolding
        return json.dumps(
            {
                "service_name": "payments-svc",
                "description": "Handles checkout payments.",
                "endpoints": [
                    {"method": "POST", "path": "/charge", "summary": "Charge a card"}
                ],
                "files": [{"path": "main.py", "content": "print('ok')\n"}],
            }
        )
    raise AssertionError(f"unexpected schema: {props}")


def _engine(approval) -> SnapOffEngine:
    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(_responder))
    context = ContextCore(config, llm)
    context.register_layer(
        StaticLayer(
            LayerKind.OPERATIONAL,
            [Document("op1", LayerKind.OPERATIONAL, "Checkout", "checkout failures rising")],
        )
    )
    context.map()
    return SnapOffEngine(config, llm, context, approval=approval)


def test_scan_ranks_opportunities_by_priority() -> None:
    engine = _engine(AutoDenyGate())
    opportunities = engine.scan()
    assert [o.title for o in opportunities] == ["Payments spin-off", "Minor tooling"]
    assert opportunities[0].priority == 80.0 * 0.7


def test_launch_blocked_without_approval() -> None:
    engine = _engine(AutoDenyGate())
    launch = engine.launch_best()
    assert launch is not None
    assert launch.launched is False
    assert launch.infrastructure == []
    # The repo is still generated for review even when the launch is blocked.
    assert launch.repo.spec.service_name == "payments-svc"


def test_launch_proceeds_with_approval() -> None:
    engine = _engine(AutoApproveGate())
    launch = engine.launch_best()
    assert launch is not None
    assert launch.launched is True
    assert len(launch.infrastructure) == 3
    assert launch.opportunity.title == "Payments spin-off"


def test_generated_repo_materializes_to_disk(tmp_path) -> None:
    engine = _engine(AutoApproveGate())
    launch = engine.launch_best()
    assert launch is not None
    written = launch.repo.materialize(tmp_path)
    assert (tmp_path / "main.py").read_text() == "print('ok')\n"
    assert written
