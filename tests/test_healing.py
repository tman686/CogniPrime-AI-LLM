"""Tests for the Self-Healing Compiler: monitor -> diagnose -> gated patch."""

from __future__ import annotations

import json
from typing import Any

from cogniprime.approval import AutoApproveGate, AutoDenyGate
from cogniprime.config import CogniPrimeConfig
from cogniprime.healing.compiler import SelfHealingCompiler
from cogniprime.healing.monitor import CodeUnit, HeuristicMonitor
from cogniprime.llm import LLMClient
from tests.fakes import FakeSDK

VULNERABLE = "password = 'hunter2'\n"


def _responder(auto_patchable: bool):
    def responder(kwargs: dict[str, Any]) -> str:
        fmt = kwargs.get("output_config", {}).get("format")
        props = set(fmt["schema"]["properties"])
        if "auto_patchable" in props:  # diagnosis
            return json.dumps(
                {
                    "category": "vulnerability",
                    "severity": "critical",
                    "explanation": "Hard-coded credential.",
                    "auto_patchable": auto_patchable,
                }
            )
        if "patched_source" in props:  # patch
            return json.dumps(
                {
                    "patched_source": "password = os.environ['PW']\n",
                    "rationale": "Move secret to environment.",
                    "changed": True,
                }
            )
        raise AssertionError(f"unexpected schema: {props}")

    return responder


def _monitor() -> HeuristicMonitor:
    monitor = HeuristicMonitor()
    monitor.register(CodeUnit("u1", "app/config.py", VULNERABLE, holding="acme"))
    return monitor


def test_monitor_flags_hard_coded_credential() -> None:
    signals = _monitor().scan()
    assert len(signals) == 1
    assert "credential" in signals[0].reason


def test_patch_blocked_without_approval() -> None:
    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(_responder(auto_patchable=True)))
    healer = SelfHealingCompiler(config, llm, _monitor(), approval=AutoDenyGate())

    report = healer.heal()
    assert report.actionable_count == 1
    assert report.proposed_patches  # a fix was generated
    assert report.applied_patches == []  # but not applied


def test_patch_applied_with_approval_and_written(tmp_path) -> None:
    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(_responder(auto_patchable=True)))
    healer = SelfHealingCompiler(config, llm, _monitor(), approval=AutoApproveGate())

    report = healer.heal(write_root=tmp_path)
    assert len(report.applied_patches) == 1
    written = (tmp_path / "app/config.py").read_text()
    assert "os.environ" in written


def test_non_auto_patchable_is_escalated_even_with_approval() -> None:
    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(_responder(auto_patchable=False)))
    healer = SelfHealingCompiler(config, llm, _monitor(), approval=AutoApproveGate())

    report = healer.heal()
    assert report.proposed_patches  # patch proposed for review
    assert report.applied_patches == []  # never auto-applied
    assert any("escalated" in line for line in report.trace)
