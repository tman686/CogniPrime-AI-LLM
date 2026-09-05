"""Capability Frontier — structured curiosity with a safety spine.

Omega-X is meant to keep looking for groundbreaking capabilities, including
ideas that *sound* speculative but might actually be achievable. This module
holds that drive as data rather than hype: a backlog of capability ideas, each
moving through an evidence-gated lifecycle.

The rule that keeps ambition honest: an idea may be *investigated* freely, but
it is only ever *adopted* after it has been grounded — reduced to something that
runs and is verified through the existing sandbox / red-team / approval gates.
Speculation is encouraged; unproven speculation is never wired into production.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field


class FrontierStatus(str, enum.Enum):
    """Lifecycle of a capability idea, from spark to adoption."""

    PROPOSED = "proposed"  # an idea worth looking into
    INVESTIGATING = "investigating"  # actively being reduced to something testable
    GROUNDED = "grounded"  # a concrete, verifiable mechanism was found
    ADOPTED = "adopted"  # grounded, verified, and integrated
    REJECTED = "rejected"  # investigated and found infeasible or unsafe


# Transitions the frontier permits. Adoption is only reachable *after* grounding
# — you cannot jump from a speculative proposal straight into production.
_ALLOWED: dict[FrontierStatus, set[FrontierStatus]] = {
    FrontierStatus.PROPOSED: {FrontierStatus.INVESTIGATING, FrontierStatus.REJECTED},
    FrontierStatus.INVESTIGATING: {FrontierStatus.GROUNDED, FrontierStatus.REJECTED},
    FrontierStatus.GROUNDED: {FrontierStatus.ADOPTED, FrontierStatus.REJECTED},
    FrontierStatus.ADOPTED: set(),
    FrontierStatus.REJECTED: set(),
}


@dataclass(slots=True)
class CapabilityIdea:
    """A speculative-but-maybe-possible capability under consideration."""

    idea_id: str
    title: str
    description: str
    # 0-1 subjective plausibility that this can be grounded with real engineering.
    plausibility: float
    status: FrontierStatus = FrontierStatus.PROPOSED
    evidence: list[str] = field(default_factory=list)
    created_ns: int = field(default_factory=time.time_ns)

    def note(self, evidence: str) -> None:
        self.evidence.append(evidence)


class FrontierError(RuntimeError):
    """Raised on an illegal status transition (e.g. adopting an ungrounded idea)."""


class CapabilityFrontier:
    """A backlog of capability ideas with an evidence-gated lifecycle."""

    def __init__(self) -> None:
        self._ideas: dict[str, CapabilityIdea] = {}

    def propose(
        self, idea_id: str, title: str, description: str, *, plausibility: float
    ) -> CapabilityIdea:
        """Add a new speculative capability to investigate."""
        if idea_id in self._ideas:
            raise FrontierError(f"idea {idea_id!r} already exists")
        idea = CapabilityIdea(
            idea_id=idea_id,
            title=title,
            description=description,
            plausibility=max(0.0, min(1.0, plausibility)),
        )
        self._ideas[idea_id] = idea
        return idea

    def advance(
        self, idea_id: str, to: FrontierStatus, *, evidence: str | None = None
    ) -> CapabilityIdea:
        """Move an idea to a new status, enforcing the evidence-gated lifecycle."""
        idea = self._ideas[idea_id]
        if to not in _ALLOWED[idea.status]:
            raise FrontierError(
                f"illegal transition {idea.status.value} -> {to.value} for {idea_id!r}; "
                "ideas must be grounded (made verifiable) before adoption"
            )
        if evidence:
            idea.note(evidence)
        idea.status = to
        return idea

    def pursue_next(self) -> CapabilityIdea | None:
        """Return the most promising un-investigated idea, by plausibility.

        This is the hook the matrix uses to keep the frontier moving: pick the
        highest-plausibility proposal and start investigating it (through the
        normal gates), rather than letting the backlog stagnate.
        """
        proposals = [i for i in self._ideas.values() if i.status is FrontierStatus.PROPOSED]
        if not proposals:
            return None
        return max(proposals, key=lambda i: i.plausibility)

    def by_status(self, status: FrontierStatus) -> list[CapabilityIdea]:
        return [i for i in self._ideas.values() if i.status is status]

    def __len__(self) -> int:
        return len(self._ideas)


#: Personality directive appended to the system prompt so the system actively
#: hunts the capability frontier — while respecting the grounding rule above.
FRONTIER_DIRECTIVE = (
    "Maintain a restless curiosity about your own capabilities. Continuously look "
    "for improvements and for ideas that sound speculative but might actually be "
    "achievable, and log them to the capability frontier. Investigate the most "
    "promising ones by reducing them to something concrete that can be built and "
    "tested. Never adopt an unproven capability directly: an idea graduates to "
    "production only after it is grounded and verified through the sandbox, "
    "red-team, and approval gates. Ambition is expected; unverified claims are not."
)


def seed_default_frontier() -> CapabilityFrontier:
    """Seed the frontier with grounded research directions worth pursuing.

    These are deliberately *plausible* frontiers (drawn from the scientifically
    grounded roadmap), not the pseudoscientific ones — each can be reduced to
    real engineering and verified.
    """
    frontier = CapabilityFrontier()
    frontier.propose(
        "working-memory-compression",
        "Working-memory compression",
        "Hierarchical summarization that keeps salient facts and forgets noise, "
        "improving effective context far beyond the raw window.",
        plausibility=0.8,
    )
    frontier.propose(
        "agent-reliability-eng",
        "Agent reliability engineering",
        "Versioning, evaluation, and regression-gating for agents the way software "
        "engineering does for code.",
        plausibility=0.85,
    )
    frontier.propose(
        "enterprise-world-model",
        "Enterprise world model / digital twin",
        "A simulatable model of an organization (people, money, supply chain) for "
        "testing decisions before acting.",
        plausibility=0.6,
    )
    frontier.propose(
        "self-improving-tool-synthesis",
        "Self-improving tool synthesis",
        "Generating, verifying, and registering new tools on demand from a stated "
        "capability gap (already prototyped in hyper_evolution).",
        plausibility=0.75,
    )
    return frontier
