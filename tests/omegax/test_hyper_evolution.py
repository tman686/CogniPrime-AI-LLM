"""Tests for the Recursive Hyper-Evolution Core."""

from __future__ import annotations

import json
from typing import Any

from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient
from omegax.core.hyper_evolution.capability_synth import CapabilitySynthesizer, ToolRegistry
from omegax.core.hyper_evolution.optimization_loop import PreferenceOptimizer, PreferencePair
from omegax.core.hyper_evolution.source_rewriter import SourceRewriter
from omegax.core.hyper_evolution.telemetry import TelemetryProfiler
from omegax.sandbox.runner import InProcessValidator
from tests.fakes import FakeSDK


def test_telemetry_ranks_hot_paths() -> None:
    profiler = TelemetryProfiler()
    profiler.record("attention", 1000)
    profiler.record("attention", 3000)
    profiler.record("embedding", 500)

    report = profiler.report()
    hot = report.hot_paths(top_k=2)
    assert hot[0].region == "attention"
    assert hot[0].calls == 2
    assert abs(hot[0].share - 4000 / 4500) < 1e-9


def test_telemetry_region_context_manager_records_time() -> None:
    profiler = TelemetryProfiler(clock=_fake_clock([0, 100]))
    with profiler.region("x"):
        pass
    trace = profiler.report().traces[0]
    assert trace.region == "x"
    assert trace.total_ns == 100


def _fake_clock(values: list[int]):
    it = iter(values)
    return lambda: next(it)


def test_source_rewriter_proposes_behavior_preserving_rewrite() -> None:
    def responder(kwargs: dict[str, Any]) -> str:
        return json.dumps(
            {
                "rewritten_source": "def f(n):\n    return n * n\n",
                "optimization": "avoid repeated multiply",
                "expected_speedup": 1.4,
                "preserves_behavior": True,
                "changed": True,
            }
        )

    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    rewriter = SourceRewriter(config, llm)

    from omegax.core.hyper_evolution.telemetry import HotPath

    hot = HotPath(region="f", total_ns=9000, calls=3, share=0.9)
    proposal = rewriter.run(hot, "def f(n):\n    return n ** 2\n").value
    assert proposal is not None
    assert proposal.expected_speedup == 1.4
    assert proposal.preserves_behavior


def test_source_rewriter_declines_unsafe_rewrite() -> None:
    def responder(kwargs: dict[str, Any]) -> str:
        return json.dumps(
            {
                "rewritten_source": "whatever",
                "optimization": "risky",
                "expected_speedup": 5.0,
                "preserves_behavior": False,  # not safe
                "changed": True,
            }
        )

    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    from omegax.core.hyper_evolution.telemetry import HotPath

    hot = HotPath("f", 1, 1, 1.0)
    assert SourceRewriter(config, llm).run(hot, "src").value is None


def test_capability_synth_verifies_before_registering() -> None:
    def responder(kwargs: dict[str, Any]) -> str:
        return json.dumps(
            {
                "name": "slugify",
                "description": "make a slug",
                "code": "def slugify(s): return s.lower()",
                "self_test": "assert True\n",
            }
        )

    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    runner = InProcessValidator(lambda _c: (True, "verified"))
    synth = CapabilitySynthesizer(config, llm, runner=runner)

    result = synth.run("need a slugify helper")
    proposal = result.value
    assert proposal is not None and proposal.verified
    registry = ToolRegistry()
    registry.register(proposal)
    assert "slugify" in registry


def test_capability_synth_reports_verification_failure() -> None:
    def responder(kwargs: dict[str, Any]) -> str:
        return json.dumps(
            {
                "name": "broken",
                "description": "x",
                "code": "def x(): ...",
                "self_test": "assert False\n",
            }
        )

    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    runner = InProcessValidator(lambda _c: (False, "self-test failed"))
    result = CapabilitySynthesizer(config, llm, runner=runner).run("gap")
    assert result.value is not None
    assert result.value.verified is False
    assert result.metadata["verified"] is False


def test_preference_optimizer_builds_dpo_records() -> None:
    def responder(kwargs: dict[str, Any]) -> str:
        return json.dumps({"preferred": "b", "margin": 0.8, "rationale": "clearer"})

    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    opt = PreferenceOptimizer(config, llm)

    records = opt.collect([PreferencePair("q", "weak answer", "strong answer")])
    assert records[0].chosen == "strong answer"
    assert records[0].rejected == "weak answer"
    assert abs(opt.mean_margin - 0.8) < 1e-9
    assert '"chosen": "strong answer"' in opt.export_dpo_dataset()
