"""The CogniPrime Agentic-OS: coordinator of the three subsystems.

:class:`CogniPrime` wires the Infinite-Context Core, the Snap-Off Engine, and
the Self-Healing Compiler into a single recursive control loop. It owns the
shared configuration, the LLM client, and the approval gate, and exposes both
individual subsystem access and a combined :meth:`tick` that runs one cycle of
the whole operating system.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cogniprime.approval import ApprovalGate, AutoDenyGate
from cogniprime.config import CogniPrimeConfig
from cogniprime.core.context_core import ContextCore
from cogniprime.core.data_layers import DataLayer
from cogniprime.healing.compiler import HealingReport, SelfHealingCompiler
from cogniprime.healing.monitor import ProductionMonitor
from cogniprime.llm import LLMClient
from cogniprime.snapoff.engine import SnapOffEngine, VentureLaunch
from cogniprime.snapoff.provisioner import Provisioner


@dataclass(slots=True)
class TickResult:
    """The outcome of one full operating-system cycle."""

    documents_mapped: int = 0
    venture: VentureLaunch | None = None
    healing: HealingReport | None = None
    trace: list[str] = field(default_factory=list)


class CogniPrime:
    """The recursive, self-healing Agentic-OS.

    Compose the OS by registering data layers and a production monitor, then
    call :meth:`tick` to run one cycle: map the empire, heal production code,
    and (with approval) spin off the highest-value new venture.
    """

    def __init__(
        self,
        config: CogniPrimeConfig | None = None,
        *,
        llm: LLMClient | None = None,
        monitor: ProductionMonitor | None = None,
        provisioner: Provisioner | None = None,
        approval: ApprovalGate | None = None,
    ) -> None:
        self.config = config or CogniPrimeConfig()
        self.llm = llm or LLMClient(self.config)
        self.approval = approval or AutoDenyGate()

        self.context = ContextCore(self.config, self.llm)
        self.snapoff = SnapOffEngine(
            self.config,
            self.llm,
            self.context,
            provisioner=provisioner,
            approval=self.approval,
        )
        self._monitor = monitor
        self.healer: SelfHealingCompiler | None = (
            SelfHealingCompiler(self.config, self.llm, monitor, approval=self.approval)
            if monitor is not None
            else None
        )

    # -- composition -------------------------------------------------------

    def register_layer(self, layer: DataLayer) -> None:
        """Register an empire data layer with the Infinite-Context Core."""
        self.context.register_layer(layer)

    def attach_monitor(self, monitor: ProductionMonitor) -> None:
        """Attach (or replace) the production monitor for the Self-Healing Compiler."""
        self._monitor = monitor
        self.healer = SelfHealingCompiler(
            self.config, self.llm, monitor, approval=self.approval
        )

    # -- control loop ------------------------------------------------------

    def tick(self, *, launch_ventures: bool = True) -> TickResult:
        """Run one cycle of the Agentic-OS.

        Order matters: map first so both downstream subsystems reason over the
        freshest context, heal production before expanding the empire, then look
        for a new venture to spin off.
        """
        result = TickResult()

        result.documents_mapped = self.context.map()
        result.trace.append(f"mapped {result.documents_mapped} documents across layers")

        if self.healer is not None:
            result.healing = self.healer.heal()
            result.trace.append(
                f"healing: {len(result.healing.applied_patches)} applied, "
                f"{result.healing.actionable_count} actionable diagnoses"
            )
        else:
            result.trace.append("healing skipped: no production monitor attached")

        if launch_ventures:
            result.venture = self.snapoff.launch_best()
            if result.venture is None:
                result.trace.append("no venture opportunities detected")
            else:
                status = "launched" if result.venture.launched else "proposed (awaiting approval)"
                result.trace.append(
                    f"venture '{result.venture.opportunity.title}' {status}"
                )

        return result
