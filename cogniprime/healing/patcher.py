"""Patch generation for the Self-Healing Compiler.

The patcher proposes a corrected version of a code unit for an actionable
:class:`~cogniprime.healing.diagnostics.Diagnosis`. It returns a :class:`Patch`
— the before/after source and a rationale — but never writes to disk itself.
Applying a patch is a separate, approval-gated step owned by the compiler.
"""

from __future__ import annotations

from dataclasses import dataclass

from cogniprime.agents.base import Agent, AgentResult
from cogniprime.config import CogniPrimeConfig
from cogniprime.healing.diagnostics import Diagnosis
from cogniprime.llm import LLMClient

_PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "patched_source": {"type": "string"},
        "rationale": {"type": "string"},
        "changed": {
            "type": "boolean",
            "description": "False if no safe fix could be produced.",
        },
    },
    "required": ["patched_source", "rationale", "changed"],
    "additionalProperties": False,
}


@dataclass(slots=True)
class Patch:
    """A proposed fix for one code unit, awaiting approval before it is applied."""

    unit_id: str
    path: str
    original_source: str
    patched_source: str
    rationale: str

    @property
    def is_noop(self) -> bool:
        return self.original_source == self.patched_source


class Patcher(Agent[Patch | None]):
    """Generates a corrected version of a code unit for a diagnosis."""

    name = "patcher"

    def __init__(self, config: CogniPrimeConfig, llm: LLMClient) -> None:
        super().__init__(config, llm)

    def run(self, diagnosis: Diagnosis) -> AgentResult[Patch | None]:
        unit = diagnosis.signal.unit
        result: AgentResult[Patch | None] = AgentResult(value=None)

        prompt = (
            "Produce a corrected version of the source below that fixes the "
            "diagnosed defect while preserving all intended behavior. Change as "
            "little as possible. If you cannot produce a safe, confident fix, set "
            "changed=false and return the original source unchanged.\n\n"
            f"Defect: {diagnosis.category} ({diagnosis.severity.value})\n"
            f"Explanation: {diagnosis.explanation}\n"
            f"Path: {unit.path}\n"
            "Source:\n"
            f"{unit.source}"
        )
        response = self.llm.structured(prompt, schema=_PATCH_SCHEMA)
        payload = response.json()

        if not payload["changed"]:
            result.log(f"no safe patch produced for {unit.unit_id}")
            return result

        patch = Patch(
            unit_id=unit.unit_id,
            path=unit.path,
            original_source=unit.source,
            patched_source=payload["patched_source"],
            rationale=payload["rationale"],
        )
        if patch.is_noop:
            result.log(f"patch for {unit.unit_id} was a no-op; discarding")
            return result

        result.value = patch
        result.log(f"generated patch for {unit.unit_id}")
        return result
