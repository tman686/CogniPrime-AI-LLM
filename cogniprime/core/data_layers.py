"""Data-layer abstractions for the Infinite-Context Core.

CogniPrime reads the entire empire through a small number of *layers* — code,
infrastructure, financial, and operational. Each layer is a source of
:class:`Document` objects that the recursive RAG loop indexes and cross-links.

Connectors to real systems (git hosts, cloud providers, ledgers) implement the
:class:`DataLayer` protocol. The in-repo :class:`StaticLayer` is a dependency-
free implementation used for tests and bootstrapping.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Iterable, Protocol, runtime_checkable


class LayerKind(str, enum.Enum):
    """The categories of data CogniPrime maps simultaneously."""

    CODE = "code"
    INFRASTRUCTURE = "infrastructure"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"


@dataclass(slots=True, frozen=True)
class Document:
    """A single indexable unit of empire context.

    Attributes:
        doc_id: Stable identifier, unique within its layer.
        layer: Which :class:`LayerKind` this document belongs to.
        title: Short human-readable label.
        content: The searchable text body.
        tags: Free-form labels used for cheap cross-layer linking.
    """

    doc_id: str
    layer: LayerKind
    title: str
    content: str
    tags: tuple[str, ...] = field(default_factory=tuple)


@runtime_checkable
class DataLayer(Protocol):
    """A source of documents for one slice of the corporate ecosystem."""

    kind: LayerKind

    def fetch(self) -> Iterable[Document]:
        """Yield the current documents for this layer.

        Implementations should be idempotent; the recursive RAG loop may call
        ``fetch`` on every mapping pass to pick up drift.
        """
        ...


@dataclass(slots=True)
class StaticLayer:
    """A :class:`DataLayer` backed by an in-memory list of documents.

    Useful for tests, seeding, and layers whose contents are supplied by an
    external ingestion step rather than pulled live.
    """

    kind: LayerKind
    documents: list[Document] = field(default_factory=list)

    def fetch(self) -> Iterable[Document]:
        return list(self.documents)

    def add(self, document: Document) -> None:
        if document.layer is not self.kind:
            raise ValueError(
                f"document layer {document.layer} does not match layer kind {self.kind}"
            )
        self.documents.append(document)
