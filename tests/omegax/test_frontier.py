"""Tests for the Capability Frontier's evidence-gated lifecycle."""

from __future__ import annotations

import pytest

from omegax.frontier import (
    CapabilityFrontier,
    FrontierError,
    FrontierStatus,
    seed_default_frontier,
)


def test_idea_must_be_grounded_before_adoption() -> None:
    frontier = CapabilityFrontier()
    frontier.propose("x", "Speculative X", "maybe possible", plausibility=0.5)

    # Cannot jump straight from PROPOSED to ADOPTED.
    with pytest.raises(FrontierError):
        frontier.advance("x", FrontierStatus.ADOPTED)

    # The legitimate path: proposed -> investigating -> grounded -> adopted.
    frontier.advance("x", FrontierStatus.INVESTIGATING, evidence="found a testable reduction")
    frontier.advance("x", FrontierStatus.GROUNDED, evidence="prototype passes sandbox")
    idea = frontier.advance("x", FrontierStatus.ADOPTED, evidence="verified + approved")
    assert idea.status is FrontierStatus.ADOPTED
    assert len(idea.evidence) == 3


def test_pursue_next_picks_highest_plausibility() -> None:
    frontier = CapabilityFrontier()
    frontier.propose("a", "A", "", plausibility=0.3)
    frontier.propose("b", "B", "", plausibility=0.9)
    frontier.propose("c", "C", "", plausibility=0.6)
    assert frontier.pursue_next().idea_id == "b"


def test_rejected_ideas_are_terminal() -> None:
    frontier = CapabilityFrontier()
    frontier.propose("x", "X", "", plausibility=0.5)
    frontier.advance("x", FrontierStatus.REJECTED, evidence="infeasible")
    with pytest.raises(FrontierError):
        frontier.advance("x", FrontierStatus.INVESTIGATING)


def test_seed_default_frontier_is_all_grounded_directions() -> None:
    frontier = seed_default_frontier()
    assert len(frontier) >= 4
    # Everything seeded is a proposal awaiting investigation, and reasonably plausible.
    proposals = frontier.by_status(FrontierStatus.PROPOSED)
    assert len(proposals) == len(frontier)
    assert all(i.plausibility >= 0.5 for i in proposals)
