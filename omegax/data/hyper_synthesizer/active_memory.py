"""High-Velocity Active Memory Layer.

Indexes solved problem-solving trajectories so temporary context becomes
permanent, queryable cognitive architecture. Two indices sit side by side:

* a **vector** index for similarity retrieval (reusing CogniPrime's store), and
* a **hypergraph** of trajectories linked by shared domains/tags, so the matrix
  can walk from one solved trajectory to related ones.

The reference implementation is in-memory and dependency-free; swap the vector
side for a production vector DB behind :class:`~cogniprime.core.memory.MemoryStore`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cogniprime.core.data_layers import Document, LayerKind
from cogniprime.core.memory import InMemoryStore, MemoryStore, Retrieval


@dataclass(slots=True, frozen=True)
class Trajectory:
    """A recorded problem-solving path worth remembering."""

    traj_id: str
    domain: str
    problem: str
    solution: str
    reward: float
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class TrajectoryLink:
    """An edge between two trajectories in the hypergraph."""

    source: str
    target: str
    reason: str


class ActiveMemoryLayer:
    """Vector + hypergraph memory over solved trajectories."""

    def __init__(self, *, store: MemoryStore | None = None) -> None:
        self._store: MemoryStore = store if store is not None else InMemoryStore()
        self._trajectories: dict[str, Trajectory] = {}
        # Adjacency: traj_id -> set of neighbor traj_ids.
        self._graph: dict[str, set[str]] = {}

    def remember(self, trajectory: Trajectory) -> list[TrajectoryLink]:
        """Index a trajectory and link it to related ones.

        Returns the new hypergraph links created (to trajectories sharing the
        domain or any tag).
        """
        self._trajectories[trajectory.traj_id] = trajectory
        self._graph.setdefault(trajectory.traj_id, set())

        # Vector side: index for similarity retrieval.
        self._store.upsert(
            Document(
                doc_id=trajectory.traj_id,
                layer=LayerKind.OPERATIONAL,
                title=f"{trajectory.domain} trajectory",
                content=f"{trajectory.problem}\n{trajectory.solution}",
                tags=trajectory.tags,
            )
        )

        # Hypergraph side: link to trajectories sharing domain or a tag.
        links: list[TrajectoryLink] = []
        for other_id, other in self._trajectories.items():
            if other_id == trajectory.traj_id:
                continue
            reason = self._relation(trajectory, other)
            if reason is None:
                continue
            self._graph[trajectory.traj_id].add(other_id)
            self._graph[other_id].add(trajectory.traj_id)
            links.append(TrajectoryLink(trajectory.traj_id, other_id, reason))
        return links

    def recall(self, query: str, *, top_k: int = 5) -> list[Retrieval]:
        """Similarity search over remembered trajectories."""
        return self._store.search(query, top_k=top_k)

    def neighbors(self, traj_id: str) -> list[Trajectory]:
        """Return trajectories directly linked to ``traj_id`` in the hypergraph."""
        return [self._trajectories[n] for n in self._graph.get(traj_id, set())]

    def __len__(self) -> int:
        return len(self._trajectories)

    @staticmethod
    def _relation(a: Trajectory, b: Trajectory) -> str | None:
        if a.domain == b.domain:
            return f"shared domain '{a.domain}'"
        shared = set(a.tags) & set(b.tags)
        if shared:
            return f"shared tags {sorted(shared)}"
        return None
