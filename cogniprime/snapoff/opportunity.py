"""Opportunity and bottleneck detection for the Snap-Off Engine.

The scanner queries the Infinite-Context Core for signals across all layers,
then asks the model to surface concrete, actionable venture opportunities with
an estimated impact and confidence. Everything is scored so the engine can act
on the highest-value opportunity first.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cogniprime.agents.base import Agent, AgentResult
from cogniprime.config import CogniPrimeConfig
from cogniprime.core.context_core import ContextCore
from cogniprime.llm import LLMClient

_OPPORTUNITY_SCHEMA = {
    "type": "object",
    "properties": {
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["bottleneck", "market"],
                    },
                    "impact_score": {"type": "number"},
                    "confidence": {"type": "number"},
                },
                "required": ["title", "rationale", "kind", "impact_score", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["opportunities"],
    "additionalProperties": False,
}


@dataclass(slots=True)
class Opportunity:
    """A detected opportunity to spin off a new line of business."""

    title: str
    rationale: str
    kind: str  # "bottleneck" | "market"
    impact_score: float
    confidence: float
    evidence_doc_ids: list[str] = field(default_factory=list)

    @property
    def priority(self) -> float:
        """Rank opportunities by expected value (impact weighted by confidence)."""
        return self.impact_score * self.confidence


class OpportunityScanner(Agent[list[Opportunity]]):
    """Surface venture opportunities from the mapped empire context."""

    name = "opportunity-scanner"

    def __init__(
        self, config: CogniPrimeConfig, llm: LLMClient, context: ContextCore
    ) -> None:
        super().__init__(config, llm)
        self.context = context

    def run(self, focus: str = "operational bottlenecks and market gaps") -> AgentResult[list[Opportunity]]:
        result: AgentResult[list[Opportunity]] = AgentResult(value=[])

        query = (
            f"Identify {focus} across the codebase, infrastructure, financials, "
            "and operations that could justify launching a new line of business."
        )
        ctx = self.context.query(query)
        result.log(f"gathered context: {len(ctx.retrievals)} documents, depth {ctx.depth_reached}")

        prompt = (
            "Based on the following analysis of the corporate ecosystem, list the "
            "most compelling opportunities to spin off a new venture. Score impact "
            "(0-100) and confidence (0-1). Be conservative with confidence when "
            "evidence is thin.\n\n"
            f"Analysis:\n{ctx.answer}"
        )
        response = self.llm.structured(prompt, schema=_OPPORTUNITY_SCHEMA)
        try:
            payload = response.json()
        except ValueError:
            result.log("opportunity extraction returned unparseable output; no opportunities")
            return result

        for item in payload.get("opportunities", []):
            result.value.append(
                Opportunity(
                    title=item["title"],
                    rationale=item["rationale"],
                    kind=item["kind"],
                    impact_score=float(item["impact_score"]),
                    confidence=float(item["confidence"]),
                    evidence_doc_ids=list(ctx.cited_doc_ids),
                )
            )

        result.value.sort(key=lambda o: o.priority, reverse=True)
        result.log(f"detected {len(result.value)} opportunities")
        return result
