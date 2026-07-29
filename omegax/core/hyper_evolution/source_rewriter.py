"""Autonomous Source Rewriter.

Given a telemetry hot path and the source of the region behind it, the rewriter
proposes a performance-optimizing rewrite. It emits a :class:`RewriteProposal`
— never a merge. Promotion is the staging pipeline's job, and merging is gated
by an :class:`~cogniprime.approval.ApprovalGate`; this daemon only authors and
argues for a change.
"""

from __future__ import annotations

from dataclasses import dataclass

from cogniprime.agents.base import Agent, AgentResult
from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient
from omegax.core.hyper_evolution.telemetry import HotPath

_REWRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "rewritten_source": {"type": "string"},
        "optimization": {"type": "string"},
        "expected_speedup": {
            "type": "number",
            "description": "Estimated multiplicative speedup, e.g. 1.5 for 1.5x.",
        },
        "preserves_behavior": {
            "type": "boolean",
            "description": "True only if the rewrite is behavior-preserving.",
        },
        "changed": {"type": "boolean"},
    },
    "required": [
        "rewritten_source",
        "optimization",
        "expected_speedup",
        "preserves_behavior",
        "changed",
    ],
    "additionalProperties": False,
}


@dataclass(slots=True)
class RewriteProposal:
    """A proposed performance rewrite for one region, awaiting review."""

    region: str
    original_source: str
    rewritten_source: str
    optimization: str
    expected_speedup: float
    preserves_behavior: bool

    @property
    def is_noop(self) -> bool:
        return self.original_source.strip() == self.rewritten_source.strip()


class SourceRewriter(Agent["RewriteProposal | None"]):
    """Proposes an optimizing rewrite for a hot region's source."""

    name = "source-rewriter"

    def __init__(self, config: CogniPrimeConfig, llm: LLMClient) -> None:
        super().__init__(config, llm)

    def run(self, hot: HotPath, source: str) -> AgentResult["RewriteProposal | None"]:
        result: AgentResult["RewriteProposal | None"] = AgentResult(value=None)
        prompt = (
            "This code region is a profiled bottleneck: "
            f"{hot.calls} calls, {hot.total_ns} ns total ({hot.share:.1%} of runtime). "
            "Propose a behavior-preserving optimization. Change as little as "
            "possible and be honest about the expected speedup. If you cannot "
            "safely improve it, set changed=false.\n\n"
            f"Region: {hot.region}\nSource:\n{source}"
        )
        response = self.llm.structured(prompt, schema=_REWRITE_SCHEMA)
        payload = response.json()

        if not payload["changed"] or not payload["preserves_behavior"]:
            result.log(f"{hot.region}: no safe behavior-preserving rewrite proposed")
            return result

        proposal = RewriteProposal(
            region=hot.region,
            original_source=source,
            rewritten_source=payload["rewritten_source"],
            optimization=payload["optimization"],
            expected_speedup=float(payload["expected_speedup"]),
            preserves_behavior=True,
        )
        if proposal.is_noop:
            result.log(f"{hot.region}: rewrite was a no-op; discarding")
            return result

        result.value = proposal
        result.log(
            f"{hot.region}: proposed rewrite ({proposal.expected_speedup:.2f}x): "
            f"{proposal.optimization}"
        )
        return result
