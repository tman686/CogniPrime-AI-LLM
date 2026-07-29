"""Continuous preference-optimization loop (RLAIF / DPO framework).

This module is the *data and scoring* half of an RLAIF/DPO pipeline — the part
that runs without a training cluster. It collects candidate responses, uses an
AI-feedback judge to build preference pairs, and exports a DPO-ready dataset of
(chosen, rejected) records plus an aggregate preference signal.

Actually updating model weights happens out of band on training infrastructure;
this loop produces the supervision that pipeline consumes. It is explicit about
that boundary rather than pretending to fine-tune in-process.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient

_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "preferred": {
            "type": "string",
            "enum": ["a", "b"],
            "description": "Which response better satisfies the prompt.",
        },
        "margin": {
            "type": "number",
            "description": "Confidence 0-1 that the preferred response is better.",
        },
        "rationale": {"type": "string"},
    },
    "required": ["preferred", "margin", "rationale"],
    "additionalProperties": False,
}


@dataclass(slots=True, frozen=True)
class PreferencePair:
    """A prompt with two candidate responses to be ranked."""

    prompt: str
    response_a: str
    response_b: str


@dataclass(slots=True, frozen=True)
class PreferenceRecord:
    """A DPO training record: chosen vs. rejected for a prompt."""

    prompt: str
    chosen: str
    rejected: str
    margin: float
    rationale: str


class PreferenceOptimizer:
    """Builds DPO-ready preference records via AI feedback (RLAIF)."""

    def __init__(self, config: CogniPrimeConfig, llm: LLMClient) -> None:
        self.config = config
        self.llm = llm
        self._records: list[PreferenceRecord] = []

    def judge(self, pair: PreferencePair) -> PreferenceRecord:
        """Rank one pair and append a preference record."""
        prompt = (
            "You are an impartial judge for RLAIF. Given a prompt and two "
            "responses, decide which better satisfies it, and how confidently.\n\n"
            f"Prompt:\n{pair.prompt}\n\n"
            f"Response A:\n{pair.response_a}\n\n"
            f"Response B:\n{pair.response_b}"
        )
        response = self.llm.structured(prompt, schema=_JUDGE_SCHEMA)
        payload = response.json()
        if payload["preferred"] == "a":
            chosen, rejected = pair.response_a, pair.response_b
        else:
            chosen, rejected = pair.response_b, pair.response_a
        record = PreferenceRecord(
            prompt=pair.prompt,
            chosen=chosen,
            rejected=rejected,
            margin=float(payload["margin"]),
            rationale=payload["rationale"],
        )
        self._records.append(record)
        return record

    def collect(self, pairs: list[PreferencePair]) -> list[PreferenceRecord]:
        """Judge a batch of pairs, returning the new records."""
        return [self.judge(pair) for pair in pairs]

    @property
    def records(self) -> list[PreferenceRecord]:
        return list(self._records)

    @property
    def mean_margin(self) -> float:
        """Aggregate preference signal — mean confidence across records."""
        if not self._records:
            return 0.0
        return sum(r.margin for r in self._records) / len(self._records)

    def export_dpo_dataset(self) -> str:
        """Serialize collected records as JSONL for a downstream DPO trainer."""
        lines = [
            json.dumps({"prompt": r.prompt, "chosen": r.chosen, "rejected": r.rejected})
            for r in self._records
        ]
        return "\n".join(lines)
