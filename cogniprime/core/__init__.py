"""CogniPrime Infinite-Context Core.

A continuous recursive RAG loop that maps the corporate ecosystem, technical
codebase, and financial architecture into a single queryable context.
"""

from cogniprime.core.context_core import ContextCore, ContextQueryResult
from cogniprime.core.data_layers import DataLayer, Document, LayerKind
from cogniprime.core.memory import InMemoryStore, MemoryStore, Retrieval

__all__ = [
    "ContextCore",
    "ContextQueryResult",
    "DataLayer",
    "Document",
    "LayerKind",
    "InMemoryStore",
    "MemoryStore",
    "Retrieval",
]
