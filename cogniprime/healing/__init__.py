"""CogniPrime Self-Healing Compiler.

An autonomous developer framework that monitors production code across all
holdings, diagnoses vulnerabilities and logic errors, and proposes patches —
applying them only through an approval gate — before systems experience
downtime.
"""

from cogniprime.healing.compiler import HealingReport, SelfHealingCompiler
from cogniprime.healing.diagnostics import Diagnosis, Diagnostician, Severity
from cogniprime.healing.monitor import CodeUnit, HealthSignal, ProductionMonitor
from cogniprime.healing.patcher import Patch, Patcher

__all__ = [
    "HealingReport",
    "SelfHealingCompiler",
    "Diagnosis",
    "Diagnostician",
    "Severity",
    "CodeUnit",
    "HealthSignal",
    "ProductionMonitor",
    "Patch",
    "Patcher",
]
