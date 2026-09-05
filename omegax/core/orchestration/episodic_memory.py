"""Episodic memory across sessions.

Stores completed episodes — a task, what was done, the outcome, and the lesson
learned — so the system retains successful debugging trajectories and failed
hypotheses beyond a single session. Recall is similarity-based over the episode
text.

The reference backend is in-memory (reusing CogniPrime's vector store). A
production deployment swaps it for a persistent store (PostgreSQL + a vector
index such as Qdrant/FAISS) behind :class:`~cogniprime.core.memory.MemoryStore`
— nothing above the store changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cogniprime.core.data_layers import Document, LayerKind
from cogniprime.core.memory import InMemoryStore, MemoryStore, Retrieval


@dataclass(slots=True, frozen=True)
class Episode:
    """A remembered task episode and its lesson."""

    episode_id: str
    task: str
    outcome: str
    success: bool
    lesson: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_text(self) -> str:
        status = "success" if self.success else "failure"
        return f"[{status}] {self.task}\nOutcome: {self.outcome}\nLesson: {self.lesson}"


class EpisodicMemory:
    """Persistent, queryable memory of past task episodes."""

    def __init__(self, *, store: MemoryStore | None = None) -> None:
        self._store: MemoryStore = store if store is not None else InMemoryStore()
        self._episodes: dict[str, Episode] = {}

    def record(self, episode: Episode) -> None:
        """Store an episode and index it for recall."""
        self._episodes[episode.episode_id] = episode
        self._store.upsert(
            Document(
                doc_id=episode.episode_id,
                layer=LayerKind.OPERATIONAL,
                title=episode.task,
                content=episode.as_text(),
                tags=episode.tags,
            )
        )

    def recall(self, query: str, *, top_k: int = 5) -> list[Episode]:
        """Return the most relevant past episodes for ``query``."""
        hits: list[Retrieval] = self._store.search(query, top_k=top_k)
        return [self._episodes[h.document.doc_id] for h in hits]

    def lessons(self, *, successful_only: bool = False) -> list[str]:
        """Return recorded lessons, optionally only from successful episodes."""
        return [
            e.lesson
            for e in self._episodes.values()
            if e.lesson and (not successful_only or e.success)
        ]

    def __len__(self) -> int:
        return len(self._episodes)
