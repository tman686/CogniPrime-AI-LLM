"""Diagnosis for the Self-Healing Compiler.

The diagnostician turns a :class:`~cogniprime.healing.monitor.HealthSignal`
into an authoritative :class:`Diagnosis`: what the defect is, how severe it is,
and whether it is safely auto-patchable. It reasons about the actual source, so
its severity supersedes the monitor's cheap hint.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from cogniprime.agents.base import Agent, AgentResult
from cogniprime.config import CogniPrimeConfig
from cogniprime.healing.monitor import HealthSignal
from cogniprime.llm import LLMClient


class Severity(str, enum.Enum):
    """Ordered severity levels for a diagnosed defect."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _SEVERITY_ORDER[self]


_SEVERITY_ORDER = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["vulnerability", "logic_error", "reliability", "none"],
        },
        "severity": {
            "type": "string",
            "enum": ["info", "low", "medium", "high", "critical"],
        },
        "explanation": {"type": "string"},
        "auto_patchable": {
            "type": "boolean",
            "description": "True only if a fix is well-understood and low-risk.",
        },
    },
    "required": ["category", "severity", "explanation", "auto_patchable"],
    "additionalProperties": False,
}


@dataclass(slots=True)
class Diagnosis:
    """An authoritative assessment of a defect in a code unit."""

    signal: HealthSignal
    category: str  # "vulnerability" | "logic_error" | "reliability" | "none"
    severity: Severity
    explanation: str
    auto_patchable: bool

    @property
    def is_actionable(self) -> bool:
        return self.category != "none" and self.severity.rank >= Severity.LOW.rank


class Diagnostician(Agent[Diagnosis]):
    """Diagnoses a single health signal against its source code."""

    name = "diagnostician"

    def __init__(self, config: CogniPrimeConfig, llm: LLMClient) -> None:
        # Diagnosis of live production defects warrants maximum rigor.
        super().__init__(config.for_subsystem(effort="max"), llm)

    def run(self, signal: HealthSignal) -> AgentResult[Diagnosis]:
        unit = signal.unit
        prompt = (
            "Diagnose the following production code unit. The monitor flagged it "
            f"for: {signal.reason}. Determine the defect category, its severity, "
            "and whether a fix is well-understood and low-risk enough to apply "
            "automatically.\n\n"
            f"Holding: {unit.holding}\n"
            f"Path: {unit.path}\n"
            "Source:\n"
            f"{unit.source}"
        )
        response = self.llm.structured(
            prompt, schema=_DIAGNOSIS_SCHEMA, effort=self.config.effort
        )
        payload = response.json()

        diagnosis = Diagnosis(
            signal=signal,
            category=payload["category"],
            severity=Severity(payload["severity"]),
            explanation=payload["explanation"],
            auto_patchable=bool(payload["auto_patchable"]),
        )
        result: AgentResult[Diagnosis] = AgentResult(value=diagnosis)
        result.log(
            f"diagnosed {unit.unit_id}: {diagnosis.category}/{diagnosis.severity.value} "
            f"(auto_patchable={diagnosis.auto_patchable})"
        )
        return result
