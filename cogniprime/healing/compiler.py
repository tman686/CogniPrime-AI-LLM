"""The Self-Healing Compiler: monitor -> diagnose -> patch -> (gated) apply.

The compiler runs the healing loop over every unhealthy code unit the monitor
surfaces. Diagnosis and patch *generation* always run; *applying* a patch is
gated by the :class:`~cogniprime.approval.ApprovalGate` because it mutates
production code. A patch that is not auto-patchable is always escalated for
review regardless of the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cogniprime.approval import ActionRequest, ApprovalGate, AutoDenyGate
from cogniprime.config import CogniPrimeConfig
from cogniprime.healing.diagnostics import Diagnosis, Diagnostician
from cogniprime.healing.monitor import ProductionMonitor
from cogniprime.healing.patcher import Patch, Patcher
from cogniprime.llm import LLMClient


@dataclass(slots=True)
class HealingReport:
    """Summary of one healing pass across the monitored holdings."""

    diagnoses: list[Diagnosis] = field(default_factory=list)
    applied_patches: list[Patch] = field(default_factory=list)
    proposed_patches: list[Patch] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)

    @property
    def actionable_count(self) -> int:
        return sum(1 for d in self.diagnoses if d.is_actionable)


class SelfHealingCompiler:
    """Autonomously heals production code, gating any live change."""

    def __init__(
        self,
        config: CogniPrimeConfig,
        llm: LLMClient,
        monitor: ProductionMonitor,
        *,
        approval: ApprovalGate | None = None,
    ) -> None:
        self.config = config
        self.llm = llm
        self.monitor = monitor
        self.approval: ApprovalGate = approval or AutoDenyGate()
        self._diagnostician = Diagnostician(config, llm)
        self._patcher = Patcher(config, llm)

    def heal(self, *, write_root: str | Path | None = None) -> HealingReport:
        """Run a full healing pass.

        When ``write_root`` is given, approved patches are written under it
        (mirroring each unit's ``path``); otherwise approved patches are
        collected in the report without touching the filesystem.
        """
        report = HealingReport()

        for signal in self.monitor.scan():
            diag_result = self._diagnostician.run(signal)
            diagnosis = diag_result.value
            report.diagnoses.append(diagnosis)
            report.trace.extend(diag_result.trace)

            if not diagnosis.is_actionable:
                continue

            patch_result = self._patcher.run(diagnosis)
            report.trace.extend(patch_result.trace)
            patch = patch_result.value
            if patch is None:
                continue

            report.proposed_patches.append(patch)
            self._maybe_apply(diagnosis, patch, report, write_root)

        report.trace.append(
            f"healing pass complete: {len(report.applied_patches)} applied, "
            f"{len(report.proposed_patches) - len(report.applied_patches)} awaiting review"
        )
        return report

    def _maybe_apply(
        self,
        diagnosis: Diagnosis,
        patch: Patch,
        report: HealingReport,
        write_root: str | Path | None,
    ) -> None:
        # Non-auto-patchable fixes always require a human, regardless of the gate.
        if not diagnosis.auto_patchable:
            report.trace.append(f"{patch.unit_id}: escalated for review (not auto-patchable)")
            return

        request = ActionRequest(
            kind="apply_patch",
            summary=f"Apply {diagnosis.severity.value} {diagnosis.category} fix to {patch.path}",
            reversible=True,  # patches are version-controlled and revertible
        )
        if self.config.require_human_approval and not self.approval.review(request):
            report.trace.append(f"{patch.unit_id}: patch proposed but approval denied")
            return

        if write_root is not None:
            target = Path(write_root) / patch.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patch.patched_source, encoding="utf-8")
            report.trace.append(f"{patch.unit_id}: patch written to {target}")

        report.applied_patches.append(patch)
        report.trace.append(f"{patch.unit_id}: patch applied")
