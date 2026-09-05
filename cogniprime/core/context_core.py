"""The Infinite-Context Core: a continuous recursive RAG loop.

``ContextCore`` does two things:

1. **map** — pull documents from every registered :class:`DataLayer` and index
   them into the :class:`MemoryStore`, cross-linking the code, infrastructure,
   financial, and operational layers.
2. **query** — answer a question by *recursively* retrieving context: an
   initial retrieval seeds an answer, the model proposes follow-up sub-queries
   to fill gaps, and the loop expands until it converges or hits
   ``max_recursion_depth``.

The recursion is what makes the context "infinite" in practice: rather than a
single top-k lookup, the core keeps pulling adjacent context across layers
until the model reports it has enough to answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from cogniprime.config import CogniPrimeConfig
from cogniprime.core.data_layers import DataLayer, LayerKind
from cogniprime.core.memory import InMemoryStore, MemoryStore, Retrieval
from cogniprime.llm import LLMClient

# Schema for the follow-up planning step of the recursive loop.
_EXPANSION_SCHEMA = {
    "type": "object",
    "properties": {
        "sufficient": {
            "type": "boolean",
            "description": "True if the retrieved context is enough to answer.",
        },
        "follow_up_queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Additional retrieval queries that would close gaps.",
        },
    },
    "required": ["sufficient", "follow_up_queries"],
    "additionalProperties": False,
}


@dataclass(slots=True)
class ContextQueryResult:
    """The synthesized answer to a context query plus its provenance."""

    answer: str
    retrievals: list[Retrieval] = field(default_factory=list)
    depth_reached: int = 0
    trace: list[str] = field(default_factory=list)

    @property
    def cited_doc_ids(self) -> list[str]:
        return [r.document.doc_id for r in self.retrievals]


class ContextCore:
    """Recursive RAG engine over the empire's data layers."""

    def __init__(
        self,
        config: CogniPrimeConfig,
        llm: LLMClient,
        *,
        store: MemoryStore | None = None,
    ) -> None:
        self.config = config
        self.llm = llm
        self.store: MemoryStore = store if store is not None else InMemoryStore()
        self._layers: dict[LayerKind, DataLayer] = {}

    # -- mapping -----------------------------------------------------------

    def register_layer(self, layer: DataLayer) -> None:
        """Register a data layer to be included in every mapping pass."""
        self._layers[layer.kind] = layer

    def map(self) -> int:
        """Index every registered layer into the store.

        Returns the number of documents mapped. Safe to call repeatedly; the
        store upserts by ``doc_id`` so re-mapping picks up drift without
        duplicating context.
        """
        count = 0
        for layer in self._layers.values():
            for document in layer.fetch():
                self.store.upsert(document)
                count += 1
        return count

    # -- querying ----------------------------------------------------------

    def query(self, question: str, *, top_k: int = 5) -> ContextQueryResult:
        """Answer ``question`` via a recursive retrieval loop.

        The loop retrieves, asks the model whether it has enough context, and
        expands with model-proposed follow-up queries until it converges or
        reaches ``max_recursion_depth``.
        """
        result = ContextQueryResult(answer="")
        seen_ids: set[str] = set()
        pending: list[str] = [question]

        for depth in range(self.config.max_recursion_depth):
            result.depth_reached = depth + 1
            batch = pending
            pending = []
            for q in batch:
                for retrieval in self.store.search(q, top_k=top_k):
                    if retrieval.document.doc_id not in seen_ids:
                        seen_ids.add(retrieval.document.doc_id)
                        result.retrievals.append(retrieval)

            result.trace.append(
                f"depth {depth + 1}: {len(result.retrievals)} documents in context"
            )

            plan = self._plan_expansion(question, result.retrievals)
            if plan["sufficient"] or not plan["follow_up_queries"]:
                result.trace.append(f"depth {depth + 1}: context sufficient, synthesizing")
                break
            pending = plan["follow_up_queries"]
            result.trace.append(
                f"depth {depth + 1}: expanding with {len(pending)} follow-up queries"
            )

        result.answer = self._synthesize(question, result.retrievals)
        return result

    # -- internals ---------------------------------------------------------

    def _plan_expansion(self, question: str, retrievals: list[Retrieval]) -> dict:
        context = _format_context(retrievals)
        prompt = (
            f"Question: {question}\n\n"
            f"Retrieved context so far:\n{context}\n\n"
            "Decide whether this context is sufficient to answer the question "
            "fully and accurately. If not, propose specific follow-up retrieval "
            "queries (across code, infrastructure, financial, or operational "
            "layers) that would close the gaps."
        )
        response = self.llm.structured(prompt, schema=_EXPANSION_SCHEMA)
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            # Degrade safely: if planning output is unparseable, stop expanding.
            return {"sufficient": True, "follow_up_queries": []}

    def _synthesize(self, question: str, retrievals: list[Retrieval]) -> str:
        context = _format_context(retrievals)
        prompt = (
            f"Question: {question}\n\n"
            f"Context:\n{context}\n\n"
            "Answer the question using only the context above. Cite the document "
            "ids you relied on. If the context is insufficient, say so explicitly."
        )
        return self.llm.reason(prompt).text


def _format_context(retrievals: list[Retrieval]) -> str:
    if not retrievals:
        return "(no context retrieved)"
    lines = []
    for r in retrievals:
        doc = r.document
        lines.append(
            f"[{doc.doc_id} | {doc.layer.value} | score={r.score:.2f}] "
            f"{doc.title}: {doc.content}"
        )
    return "\n".join(lines)
