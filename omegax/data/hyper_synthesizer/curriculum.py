"""Adversarial Curriculum Generator.

A proposer agent generates a challenge at a target difficulty; a solver attempts
it; a critic judges the attempt. The generator uses that feedback to ratchet
difficulty adversarially — pushing just past the solver's current frontier —
producing a stream of increasingly hard, self-labeled training challenges.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from cogniprime.agents.base import Agent, AgentResult
from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient


class Difficulty(int, enum.Enum):
    """Coarse difficulty bands for generated challenges."""

    FOUNDATION = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    FRONTIER = 4
    BEYOND = 5

    def next(self) -> "Difficulty":
        return Difficulty(min(self.value + 1, Difficulty.BEYOND.value))


_CHALLENGE_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "prompt": {"type": "string"},
        "reference_solution": {"type": "string"},
        "verifiable": {
            "type": "boolean",
            "description": "True if the answer can be checked mechanically.",
        },
        "checker_code": {
            "type": "string",
            "description": "Optional Python that exits non-zero if a solution is wrong.",
        },
    },
    "required": ["domain", "prompt", "reference_solution", "verifiable", "checker_code"],
    "additionalProperties": False,
}

_CRITIQUE_SCHEMA = {
    "type": "object",
    "properties": {
        "solved": {"type": "boolean"},
        "escalate": {
            "type": "boolean",
            "description": "True if difficulty should increase next round.",
        },
        "notes": {"type": "string"},
    },
    "required": ["solved", "escalate", "notes"],
    "additionalProperties": False,
}


@dataclass(slots=True)
class Challenge:
    """A generated challenge with an optional mechanical checker."""

    domain: str
    prompt: str
    reference_solution: str
    difficulty: Difficulty
    verifiable: bool
    checker_code: str = ""


class CurriculumGenerator(Agent[Challenge]):
    """Generates challenges and adversarially ratchets difficulty."""

    name = "curriculum-generator"

    def __init__(self, config: CogniPrimeConfig, llm: LLMClient) -> None:
        super().__init__(config, llm)

    def generate(self, domain: str, difficulty: Difficulty) -> Challenge:
        """Generate a single challenge at ``difficulty`` in ``domain``."""
        prompt = (
            f"Generate a {difficulty.name.lower()} challenge in the domain "
            f"'{domain}'. Provide a reference solution and, where the answer can "
            "be checked mechanically, a Python checker snippet that exits with a "
            "non-zero code when a submitted solution is wrong."
        )
        payload = self.llm.structured(prompt, schema=_CHALLENGE_SCHEMA).json()
        return Challenge(
            domain=payload["domain"],
            prompt=payload["prompt"],
            reference_solution=payload["reference_solution"],
            difficulty=difficulty,
            verifiable=bool(payload["verifiable"]),
            checker_code=payload["checker_code"],
        )

    def run(
        self,
        domain: str = "systems reasoning",
        *,
        start: Difficulty = Difficulty.INTERMEDIATE,
        rounds: int = 3,
    ) -> AgentResult[Challenge]:
        """Run an adversarial curriculum loop and return the hardest challenge.

        Each round generates a challenge, has a solver attempt it, and lets a
        critic decide whether to escalate. Difficulty rises whenever the solver
        clears the frontier, so the returned challenge sits at the edge of what
        the solver can currently handle.
        """
        difficulty = start
        latest: Challenge | None = None
        result: AgentResult[Challenge] = AgentResult(value=None)  # type: ignore[arg-type]

        for round_no in range(rounds):
            challenge = self.generate(domain, difficulty)
            latest = challenge

            attempt = self.llm.reason(
                f"Solve this {domain} challenge:\n{challenge.prompt}"
            ).text
            critique = self.llm.structured(
                (
                    "Grade this solution attempt against the reference. Decide "
                    "whether it is solved and whether to escalate difficulty.\n\n"
                    f"Challenge:\n{challenge.prompt}\n\n"
                    f"Reference:\n{challenge.reference_solution}\n\n"
                    f"Attempt:\n{attempt}"
                ),
                schema=_CRITIQUE_SCHEMA,
            ).json()

            result.log(
                f"round {round_no + 1}: difficulty={difficulty.name} "
                f"solved={critique['solved']} escalate={critique['escalate']}"
            )
            if critique["escalate"]:
                difficulty = difficulty.next()

        result.value = latest  # type: ignore[assignment]
        return result
