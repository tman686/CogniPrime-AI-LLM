"""Tests for the Infinite-Context Core: memory store and recursive RAG loop."""

from __future__ import annotations

import json
from typing import Any

from cogniprime.config import CogniPrimeConfig
from cogniprime.core.context_core import ContextCore
from cogniprime.core.data_layers import Document, LayerKind, StaticLayer
from cogniprime.core.memory import InMemoryStore
from cogniprime.llm import LLMClient
from tests.fakes import FakeSDK


def _doc(doc_id: str, layer: LayerKind, title: str, content: str) -> Document:
    return Document(doc_id=doc_id, layer=layer, title=title, content=content)


def test_memory_store_ranks_by_relevance() -> None:
    store = InMemoryStore()
    store.upsert(_doc("a", LayerKind.CODE, "Auth", "login authentication tokens"))
    store.upsert(_doc("b", LayerKind.FINANCIAL, "Revenue", "quarterly revenue growth"))

    results = store.search("authentication login")
    assert results
    assert results[0].document.doc_id == "a"


def test_memory_store_layer_filter() -> None:
    store = InMemoryStore()
    store.upsert(_doc("a", LayerKind.CODE, "Auth", "authentication service"))
    store.upsert(_doc("b", LayerKind.FINANCIAL, "Auth spend", "authentication vendor cost"))

    results = store.search("authentication", layer=LayerKind.FINANCIAL)
    assert [r.document.doc_id for r in results] == ["b"]


def test_context_core_recursive_loop_expands_then_converges() -> None:
    # Responder: first expansion asks for a follow-up, second says sufficient.
    expansion_calls = {"n": 0}

    def responder(kwargs: dict[str, Any]) -> str:
        fmt = kwargs.get("output_config", {}).get("format")
        if fmt is not None:
            # This is the expansion-planning structured call.
            expansion_calls["n"] += 1
            if expansion_calls["n"] == 1:
                return json.dumps(
                    {"sufficient": False, "follow_up_queries": ["scaling latency"]}
                )
            return json.dumps({"sufficient": True, "follow_up_queries": []})
        # Free-text synthesis call.
        return "Synthesized answer citing [svc]."

    config = CogniPrimeConfig(api_key="test", max_recursion_depth=4)
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    core = ContextCore(config, llm)

    layer = StaticLayer(
        kind=LayerKind.CODE,
        documents=[
            _doc("svc", LayerKind.CODE, "Service", "authentication service latency scaling"),
        ],
    )
    core.register_layer(layer)
    assert core.map() == 1

    result = core.query("How healthy is the authentication service?")
    assert result.answer == "Synthesized answer citing [svc]."
    assert result.depth_reached == 2  # expanded once, then converged
    assert "svc" in result.cited_doc_ids


def test_context_core_respects_max_recursion_depth() -> None:
    # Responder never reports sufficient; loop must stop at max depth.
    def responder(kwargs: dict[str, Any]) -> str:
        if kwargs.get("output_config", {}).get("format") is not None:
            return json.dumps({"sufficient": False, "follow_up_queries": ["more"]})
        return "answer"

    config = CogniPrimeConfig(api_key="test", max_recursion_depth=2)
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    core = ContextCore(config, llm)
    core.register_layer(
        StaticLayer(LayerKind.CODE, [_doc("d", LayerKind.CODE, "T", "more context here")])
    )
    core.map()

    result = core.query("q")
    assert result.depth_reached == 2
