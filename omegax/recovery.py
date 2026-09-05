"""Frictionless Self-Healing Architecture.

When an exception surfaces, the recovery engine captures the traceback, asks the
model to diagnose the fault and propose a corrected version of the failing
source, and returns a :class:`RecoveryProposal`. Two things stay safe:

* **Auto-recovery** (retry, rollback to last good snapshot) is fully automatic —
  it is reversible and restores known-good state.
* **Applying a code patch** is a proposal only, promoted through the same staging
  pipeline and approval gate as any other self-modification.

So the system resumes autonomously via rollback/retry, while self-authored code
fixes remain gated — no unreviewed patch reaches production.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass

from cogniprime.agents.base import Agent, AgentResult
from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient

_RECOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "patched_source": {"type": "string"},
        "confidence": {"type": "number"},
        "changed": {"type": "boolean"},
    },
    "required": ["root_cause", "patched_source", "confidence", "changed"],
    "additionalProperties": False,
}


@dataclass(slots=True)
class RecoveryProposal:
    """A diagnosed fault and a proposed (gated) code fix."""

    root_cause: str
    original_source: str
    patched_source: str
    confidence: float
    changed: bool

    @property
    def has_fix(self) -> bool:
        return self.changed and self.patched_source.strip() != self.original_source.strip()


class RecoveryEngine(Agent[RecoveryProposal]):
    """Diagnoses an exception and proposes a fix for the failing source."""

    name = "recovery-engine"

    def __init__(self, config: CogniPrimeConfig, llm: LLMClient) -> None:
        # Live incident recovery warrants maximum rigor.
        super().__init__(config.for_subsystem(effort="max"), llm)

    def diagnose(self, exc: BaseException, source: str) -> AgentResult[RecoveryProposal]:
        """Diagnose ``exc`` against ``source`` and propose a fix."""
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return self._run_with_traceback(tb, source)

    def run(self, tb_text: str, source: str) -> AgentResult[RecoveryProposal]:
        """Diagnose from a raw traceback string (for logs / replayed faults)."""
        return self._run_with_traceback(tb_text, source)

    def _run_with_traceback(self, tb_text: str, source: str) -> AgentResult[RecoveryProposal]:
        prompt = (
            "A production exception occurred. Identify the root cause from the "
            "traceback and propose a minimal corrected version of the source. If "
            "you cannot produce a confident, safe fix, set changed=false.\n\n"
            f"Traceback:\n{tb_text}\n\nSource:\n{source}"
        )
        payload = self.llm.structured(
            prompt, schema=_RECOVERY_SCHEMA, effort=self.config.effort
        ).json()
        proposal = RecoveryProposal(
            root_cause=payload["root_cause"],
            original_source=source,
            patched_source=payload["patched_source"],
            confidence=float(payload["confidence"]),
            changed=bool(payload["changed"]),
        )
        result: AgentResult[RecoveryProposal] = AgentResult(value=proposal)
        result.log(
            f"diagnosed root cause: {proposal.root_cause} "
            f"(fix proposed={proposal.has_fix}, confidence={proposal.confidence:.2f})"
        )
        return result
