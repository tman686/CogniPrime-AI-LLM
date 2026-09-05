"""Tests for the top-level CogniPrime Agentic-OS control loop."""

from __future__ import annotations

import json
from typing import Any

from cogniprime.approval import AutoApproveGate
from cogniprime.config import CogniPrimeConfig
from cogniprime.core.data_layers import Document, LayerKind, StaticLayer
from cogniprime.healing.monitor import CodeUnit, HeuristicMonitor
from cogniprime.llm import LLMClient
from cogniprime.orchestrator import CogniPrime
from tests.fakes import FakeSDK


def _responder(kwargs: dict[str, Any]) -> str:
    fmt = kwargs.get("output_config", {}).get("format")
    if fmt is None:
        return "analysis"
    props = set(fmt["schema"]["properties"])
    if "follow_up_queries" in props:
        return json.dumps({"sufficient": True, "follow_up_queries": []})
    if "opportunities" in props:
        return json.dumps(
            {
                "opportunities": [
                    {
                        "title": "Logistics venture",
                        "rationale": "Fulfillment delays.",
                        "kind": "bottleneck",
                        "impact_score": 60.0,
                        "confidence": 0.6,
                    }
                ]
            }
        )
    if "service_name" in props:
        return json.dumps(
            {
                "service_name": "logistics-svc",
                "description": "Routes shipments.",
                "endpoints": [{"method": "GET", "path": "/routes", "summary": "List routes"}],
                "files": [{"path": "app.py", "content": "x = 1\n"}],
            }
        )
    if "auto_patchable" in props:
        return json.dumps(
            {
                "category": "reliability",
                "severity": "medium",
                "explanation": "Bare except swallows errors.",
                "auto_patchable": True,
            }
        )
    if "patched_source" in props:
        return json.dumps(
            {
                "patched_source": "try:\n    run()\nexcept ValueError:\n    handle()\n",
                "rationale": "Catch a specific exception.",
                "changed": True,
            }
        )
    raise AssertionError(f"unexpected schema: {props}")


def _os(approval) -> CogniPrime:
    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(_responder))
    os = CogniPrime(config, llm=llm, approval=approval)
    os.register_layer(
        StaticLayer(
            LayerKind.OPERATIONAL,
            [Document("op", LayerKind.OPERATIONAL, "Fulfillment", "shipment delays growing")],
        )
    )
    monitor = HeuristicMonitor()
    monitor.register(
        CodeUnit("u", "svc/worker.py", "try:\n    run()\nexcept:\n    pass\n", holding="acme")
    )
    os.attach_monitor(monitor)
    return os


def test_full_tick_maps_heals_and_launches_with_approval() -> None:
    os = _os(AutoApproveGate())
    result = os.tick()

    assert result.documents_mapped == 1
    assert result.healing is not None
    assert len(result.healing.applied_patches) == 1
    assert result.venture is not None
    assert result.venture.launched is True
    assert result.venture.opportunity.title == "Logistics venture"


def test_tick_without_monitor_skips_healing() -> None:
    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(_responder))
    os = CogniPrime(config, llm=llm, approval=AutoApproveGate())
    os.register_layer(
        StaticLayer(LayerKind.CODE, [Document("c", LayerKind.CODE, "M", "module code")])
    )

    result = os.tick(launch_ventures=False)
    assert result.healing is None
    assert result.venture is None
    assert any("healing skipped" in line for line in result.trace)
