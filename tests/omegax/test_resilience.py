"""Tests for Fault-Tolerance, Chaos Engineering & Distillation."""

from __future__ import annotations

from typing import Any

import pytest

from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient
from omegax.core.resilience.chaos import ChaosInjector, FaultKind
from omegax.core.resilience.distillation import (
    DistillationError,
    DistillationPipeline,
    SourceKind,
    SourceRecord,
)
from omegax.core.resilience.ledger import CryptographicLedger
from tests.fakes import FakeSDK


def test_ledger_is_hash_chained_and_verifiable() -> None:
    ledger = CryptographicLedger(clock=lambda: 0)
    ledger.append("evolve", region="attention")
    ledger.append("evaluate", objective=0.9)
    assert len(ledger) == 2
    assert ledger.verify()
    # Each entry commits to the previous entry's hash.
    assert ledger.entries[1].prev_hash == ledger.entries[0].entry_hash


def test_ledger_detects_tampering() -> None:
    ledger = CryptographicLedger(clock=lambda: 0)
    ledger.append("evolve", region="a")
    ledger.append("evolve", region="b")
    # Tamper with a committed payload after the fact.
    object.__setattr__(ledger.entries[0], "payload", {"region": "HACKED"})
    assert ledger.verify() is False


def test_chaos_injector_reports_survival() -> None:
    injector = ChaosInjector(seed=1)

    def robust() -> None:
        return None

    def fragile() -> None:
        raise ValueError("boom")

    assert injector.inject_exception(robust).survived is True
    result = injector.inject_exception(fragile)
    assert result.survived is False
    assert result.fault is FaultKind.EXCEPTION
    assert "ValueError" in result.detail


def test_chaos_context_corruption_is_deterministic() -> None:
    a = ChaosInjector(seed=7).corrupt_context("the quick brown fox")[0]
    b = ChaosInjector(seed=7).corrupt_context("the quick brown fox")[0]
    assert a == b  # seeded -> reproducible
    assert len(a) < len("the quick brown fox")


def test_distillation_rejects_proprietary_sources() -> None:
    def responder(kwargs: dict[str, Any]) -> str:
        return "reconstructed reasoning"

    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    pipe = DistillationPipeline(config, llm)

    proprietary = SourceRecord("s1", SourceKind.PROPRIETARY_API, "q", "a")
    with pytest.raises(DistillationError):
        pipe.ingest(proprietary)
    assert pipe.rejected and pipe.rejected[0].source_id == "s1"


def test_distillation_ingests_permitted_sources() -> None:
    def responder(kwargs: dict[str, Any]) -> str:
        return "clean reasoning path"

    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    pipe = DistillationPipeline(config, llm)

    records = [
        SourceRecord("s1", SourceKind.PUBLIC_BENCHMARK, "prove associativity", "QED"),
        SourceRecord("s2", SourceKind.PROPRIETARY_API, "leaked", "x"),  # skipped
        SourceRecord("s3", SourceKind.OPEN_WEIGHTS, "sort a list", "[1,2,3]"),
    ]
    samples = pipe.ingest_many(records)
    assert {s.source_id for s in samples} == {"s1", "s3"}
    assert len(pipe.rejected) == 1
