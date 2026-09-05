"""Memory store abstraction for the Infinite-Context Core.

The recursive RAG loop needs a retrieval surface it can write to and query.
:class:`MemoryStore` is the interface; :class:`InMemoryStore` is a dependency-
free reference implementation using a lightweight lexical similarity score.

A production deployment swaps :class:`InMemoryStore` for a vector database
(e.g. a pgvector or a managed index) behind the same interface — no subsystem
above the store needs to change.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from cogniprime.core.data_layers import Document, LayerKind

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


@dataclass(slots=True, frozen=True)
class Retrieval:
    """A retrieved document paired with its relevance score."""

    document: Document
    score: float


class MemoryStore(Protocol):
    """A writable, queryable index over empire documents."""

    def upsert(self, document: Document) -> None:
        """Insert or replace a document by its ``doc_id``."""
        ...

    def search(
        self, query: str, *, layer: LayerKind | None = None, top_k: int = 5
    ) -> list[Retrieval]:
        """Return the ``top_k`` most relevant documents for ``query``."""
        ...

    def __len__(self) -> int:
        ...


class InMemoryStore:
    """Reference :class:`MemoryStore` using cosine similarity over term counts.

    Intentionally simple and deterministic so subsystems can be tested without
    external services. The scoring is lexical (bag-of-words cosine), which is
    enough to exercise the recursive RAG control flow end to end.
    """

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self._vectors: dict[str, Counter[str]] = {}

    def upsert(self, document: Document) -> None:
        self._docs[document.doc_id] = document
        text = f"{document.title} {document.content} {' '.join(document.tags)}"
        self._vectors[document.doc_id] = Counter(_tokenize(text))

    def search(
        self, query: str, *, layer: LayerKind | None = None, top_k: int = 5
    ) -> list[Retrieval]:
        q_vec = Counter(_tokenize(query))
        if not q_vec:
            return []
        results: list[Retrieval] = []
        for doc_id, doc in self._docs.items():
            if layer is not None and doc.layer is not layer:
                continue
            score = _cosine(q_vec, self._vectors[doc_id])
            if score > 0.0:
                results.append(Retrieval(document=doc, score=score))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def __len__(self) -> int:
        return len(self._docs)


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    if dot == 0:
        return 0.0
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return dot / (norm_a * norm_b)
