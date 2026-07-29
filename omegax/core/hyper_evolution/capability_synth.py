"""Dynamic Capability Synthesizer.

Generates new tools/capabilities (e.g. an API wrapper or a small execution
library) on demand from a capability gap. A synthesized capability is sandbox-
verified and only *registered* for use when the registration gate approves — an
unapproved capability is retained as a proposal, never activated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cogniprime.agents.base import Agent, AgentResult
from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient
from omegax.sandbox.runner import SandboxReport, SandboxRunner

_CAPABILITY_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "code": {"type": "string"},
        "self_test": {
            "type": "string",
            "description": "A standalone snippet that exercises the capability.",
        },
    },
    "required": ["name", "description", "code", "self_test"],
    "additionalProperties": False,
}


@dataclass(slots=True)
class CapabilityProposal:
    """A synthesized capability awaiting verification and registration."""

    name: str
    description: str
    code: str
    self_test: str
    verification: SandboxReport | None = None
    registered: bool = False

    @property
    def verified(self) -> bool:
        return self.verification is not None and self.verification.passed


@dataclass(slots=True)
class ToolRegistry:
    """The set of capabilities currently active in the matrix."""

    tools: dict[str, CapabilityProposal] = field(default_factory=dict)

    def register(self, capability: CapabilityProposal) -> None:
        capability.registered = True
        self.tools[capability.name] = capability

    def __contains__(self, name: str) -> bool:
        return name in self.tools

    def __len__(self) -> int:
        return len(self.tools)


class CapabilitySynthesizer(Agent[CapabilityProposal | None]):
    """Synthesizes and verifies a new capability for a stated gap."""

    name = "capability-synthesizer"

    def __init__(
        self,
        config: CogniPrimeConfig,
        llm: LLMClient,
        *,
        runner: SandboxRunner,
    ) -> None:
        super().__init__(config, llm)
        self.runner = runner

    def run(self, capability_gap: str) -> AgentResult[CapabilityProposal | None]:
        result: AgentResult[CapabilityProposal | None] = AgentResult(value=None)
        prompt = (
            "Design a small, self-contained Python capability that fills this "
            "gap. Provide the implementation and a standalone self-test snippet "
            "that returns a non-zero exit code on failure.\n\n"
            f"Capability gap: {capability_gap}"
        )
        response = self.llm.structured(prompt, schema=_CAPABILITY_SCHEMA)
        payload = response.json()

        proposal = CapabilityProposal(
            name=payload["name"],
            description=payload["description"],
            code=payload["code"],
            self_test=payload["self_test"],
        )
        proposal.verification = self.runner.verify(proposal.self_test)
        if not proposal.verified:
            result.log(
                f"capability '{proposal.name}' failed sandbox verification: "
                f"{proposal.verification.detail}"
            )
            # Still return the proposal so it can be inspected/repaired.
            result.value = proposal
            result.metadata["verified"] = False
            return result

        result.value = proposal
        result.metadata["verified"] = True
        result.log(f"synthesized and verified capability '{proposal.name}'")
        return result
