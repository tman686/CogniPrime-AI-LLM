"""Tests for the Autonomous Knowledge & Synthesis Engine."""

from __future__ import annotations

import json
from typing import Any

from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient
from omegax.data.hyper_synthesizer.active_memory import ActiveMemoryLayer, Trajectory
from omegax.data.hyper_synthesizer.curriculum import Challenge, CurriculumGenerator, Difficulty
from omegax.data.hyper_synthesizer.verification import VerificationHarvester
from omegax.sandbox.runner import InProcessValidator
from tests.fakes import FakeSDK


def test_curriculum_escalates_difficulty_when_solver_succeeds() -> None:
    def responder(kwargs: dict[str, Any]) -> str:
        fmt = kwargs.get("output_config", {}).get("format")
        if fmt is None:
            return "an attempt"
        props = set(fmt["schema"]["properties"])
        if "checker_code" in props:  # challenge generation
            return json.dumps(
                {
                    "domain": "math",
                    "prompt": "prove X",
                    "reference_solution": "proof",
                    "verifiable": True,
                    "checker_code": "assert True\n",
                }
            )
        if "escalate" in props:  # critique
            return json.dumps({"solved": True, "escalate": True, "notes": "ok"})
        raise AssertionError(props)

    config = CogniPrimeConfig(api_key="test")
    llm = LLMClient(config, sdk_client=FakeSDK(responder))
    gen = CurriculumGenerator(config, llm)

    result = gen.run("math", start=Difficulty.FOUNDATION, rounds=2)
    # Two escalations from FOUNDATION -> the last generated challenge sits higher.
    assert result.value is not None
    assert result.value.difficulty.value >= Difficulty.INTERMEDIATE.value


def test_verification_harvester_keeps_only_passing_samples() -> None:
    runner = InProcessValidator(lambda code: ("VALID" in code, "checked"))
    harvester = VerificationHarvester(runner)

    good = Challenge("math", "p", "ref", Difficulty.INTERMEDIATE, True, "assert 'VALID'\n")
    bad = Challenge("math", "p2", "ref", Difficulty.INTERMEDIATE, True, "assert 'NOPE'\n")

    assert harvester.harvest(good, "sol") is not None
    assert harvester.harvest(bad, "sol") is None
    assert len(harvester.kept) == 1
    assert harvester.yield_rate == 0.5


def test_verification_harvester_drops_non_verifiable() -> None:
    runner = InProcessValidator(lambda _c: (True, "ok"))
    harvester = VerificationHarvester(runner)
    challenge = Challenge("essay", "write", "ref", Difficulty.FOUNDATION, False, "")
    assert harvester.harvest(challenge, "sol") is None
    assert harvester.rejected == 1


def test_verification_harvester_binds_solution_into_checker() -> None:
    # Checker references `solution`, which the harvester binds from the arg.
    runner = InProcessValidator(
        lambda code: ("solution = '42'" in code, "solution was bound")
    )
    harvester = VerificationHarvester(runner)
    challenge = Challenge(
        "math", "answer", "42", Difficulty.FOUNDATION, True, "assert solution == '42'\n"
    )
    assert harvester.harvest(challenge, "42") is not None


def test_active_memory_links_by_shared_domain() -> None:
    mem = ActiveMemoryLayer()
    mem.remember(Trajectory("t1", "math", "p1", "s1", 1.0, ("proofs",)))
    links = mem.remember(Trajectory("t2", "math", "p2", "s2", 1.0, ("algebra",)))
    assert len(mem) == 2
    assert any(link.target == "t1" for link in links)
    assert {t.traj_id for t in mem.neighbors("t2")} == {"t1"}


def test_active_memory_recall_finds_similar_trajectory() -> None:
    mem = ActiveMemoryLayer()
    mem.remember(Trajectory("t1", "code", "sorting algorithm quicksort", "s", 1.0))
    mem.remember(Trajectory("t2", "finance", "revenue projection model", "s", 1.0))
    hits = mem.recall("quicksort sorting")
    assert hits and hits[0].document.doc_id == "t1"
