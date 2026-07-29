"""The Omega-X Matrix: the recursive self-improvement control loop.

``OmegaMatrix`` wires the five module groups into one cycle:

1. **Profile** — telemetry surfaces the hot paths (module A).
2. **Meta-reason & self-compile** — propose rewrites for hot paths, verify them
   in the sandbox, and (only through the approval gate) atomically promote them
   via the staging pipeline (modules A + engineering spec).
3. **Evaluate** — score the result against a benchmark suite through the
   supremacy objective; the regression shield auto-rolls-back any regression
   (module C).
4. **Synthesize** — generate an adversarial challenge, verify solutions, and
   commit solved trajectories to active memory (module B).

Every self-modification, promotion, rollback, and synthesis event is written to
the append-only :class:`CryptographicLedger`, so the whole cycle leaves a
tamper-evident trail (module E). Irreversible steps are gated; rollback is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cogniprime.approval import ActionRequest, ApprovalGate, AutoDenyGate
from cogniprime.llm import LLMClient
from omegax.config import OmegaConfig
from omegax.core.hyper_evolution.capability_synth import CapabilitySynthesizer, ToolRegistry
from omegax.core.hyper_evolution.source_rewriter import RewriteProposal, SourceRewriter
from omegax.core.hyper_evolution.telemetry import HotPath, TelemetryProfiler
from omegax.core.resilience.ledger import CryptographicLedger
from omegax.data.hyper_synthesizer.active_memory import ActiveMemoryLayer, Trajectory
from omegax.data.hyper_synthesizer.curriculum import CurriculumGenerator, Difficulty
from omegax.data.hyper_synthesizer.verification import VerificationHarvester
from omegax.eval.supremacy.benchmark import BenchmarkSuite, Harvester, SystemFn
from omegax.eval.supremacy.objective import SupremacyObjective
from omegax.eval.supremacy.regression import RegressionShield, RegressionVerdict
from omegax.recovery import RecoveryEngine
from omegax.sandbox.runner import InProcessValidator, SandboxRunner
from omegax.sandbox.staging import Candidate, StageOutcome, StagingPipeline, ValidationResult


@dataclass(slots=True)
class EvolutionResult:
    """Outcome of trying to evolve one hot path."""

    region: str
    proposal: RewriteProposal | None
    outcome: StageOutcome | None
    committed: bool


@dataclass(slots=True)
class EvaluationResult:
    """Outcome of the evaluation + regression-shield stage."""

    objective: float
    verdict: RegressionVerdict
    rolled_back: bool


@dataclass(slots=True)
class CycleReport:
    """The full record of one matrix cycle."""

    hot_paths: list[HotPath] = field(default_factory=list)
    evolutions: list[EvolutionResult] = field(default_factory=list)
    evaluation: EvaluationResult | None = None
    trajectories_remembered: int = 0
    trace: list[str] = field(default_factory=list)
    ledger_verified: bool = True


class OmegaMatrix:
    """The recursive self-improvement operating loop."""

    def __init__(
        self,
        config: OmegaConfig | None = None,
        *,
        llm: LLMClient | None = None,
        approval: ApprovalGate | None = None,
        runner: SandboxRunner | None = None,
        source_map: dict[str, str] | None = None,
        objective: SupremacyObjective | None = None,
    ) -> None:
        self.config = config or OmegaConfig()
        cp = self.config.to_cogniprime()
        self.llm = llm or LLMClient(cp)
        self.approval = approval or AutoDenyGate()
        # Safe default: never executes candidate source.
        self.runner = runner or InProcessValidator(lambda _c: (True, "default no-op validator"))

        self.ledger = CryptographicLedger()
        self.profiler = TelemetryProfiler()
        self.registry = ToolRegistry()
        self.memory = ActiveMemoryLayer()
        self.objective = objective or SupremacyObjective()
        self.shield = RegressionShield()
        # The evolvable "live code" state: region -> current source.
        self.staging = StagingPipeline(dict(source_map or {}), self.runner)

        self._rewriter = SourceRewriter(cp, self.llm)
        self._synthesizer = CapabilitySynthesizer(cp, self.llm, runner=self.runner)
        self._curriculum = CurriculumGenerator(cp, self.llm)
        self._harvester = VerificationHarvester(self.runner)
        self._recovery = RecoveryEngine(cp, self.llm)

    # -- module A: evolve a hot path --------------------------------------

    def evolve(self, hot: HotPath) -> EvolutionResult:
        """Propose, verify, and (if approved) promote a rewrite for a hot path."""
        source = self.staging.state.get(hot.region)
        if source is None:
            self.ledger.append("evolve.skipped", region=hot.region, reason="no source")
            return EvolutionResult(hot.region, None, None, committed=False)

        proposal = self._rewriter.run(hot, source).value
        if proposal is None:
            self.ledger.append("evolve.no_proposal", region=hot.region)
            return EvolutionResult(hot.region, None, None, committed=False)

        candidate = Candidate(
            candidate_id=f"rw-{hot.region}",
            description=proposal.optimization,
            code=proposal.rewritten_source,
            next_state={**self.staging.state, hot.region: proposal.rewritten_source},
        )
        approved = self._approve_merge(hot.region, proposal)
        outcome = self.staging.promote(candidate, approved=approved)
        self.ledger.append(
            "evolve.promote",
            region=hot.region,
            outcome=outcome.outcome.value,
            expected_speedup=proposal.expected_speedup,
            verified=outcome.report.passed,
        )
        return EvolutionResult(
            region=hot.region,
            proposal=proposal,
            outcome=outcome.outcome,
            committed=outcome.outcome is StageOutcome.COMMITTED,
        )

    def _approve_merge(self, region: str, proposal: RewriteProposal) -> bool:
        if not self.config.gate_merges:
            return True
        request = ActionRequest(
            kind="merge_rewrite",
            summary=f"Merge {proposal.expected_speedup:.2f}x rewrite of '{region}': {proposal.optimization}",
            reversible=True,  # committed via staging; revertible by rollback
        )
        return self.approval.review(request)

    # -- module C: evaluate + regression shield ---------------------------

    def evaluate(
        self, suite: BenchmarkSuite, system: SystemFn, *, efficiency: float = 0.0
    ) -> EvaluationResult:
        """Score the system and roll back automatically on a regression."""
        result = Harvester().run(suite, system)
        objective = self.objective.score(result, efficiency=efficiency)
        verdict = self.shield.evaluate(objective)

        rolled_back = False
        if verdict is RegressionVerdict.REGRESSED and self.config.auto_rollback:
            if self.staging.snapshots:
                self.staging.rollback(self.staging.snapshots[-1])
                rolled_back = True
        else:
            # Advance the baseline on a kept result.
            self.shield.accept(objective)

        self.ledger.append(
            "evaluate",
            suite=suite.name,
            objective=objective,
            verdict=verdict.value,
            rolled_back=rolled_back,
        )
        return EvaluationResult(objective=objective, verdict=verdict, rolled_back=rolled_back)

    # -- module B: synthesize + remember ----------------------------------

    def synthesize(
        self,
        domain: str = "systems reasoning",
        *,
        difficulty: Difficulty = Difficulty.INTERMEDIATE,
        rounds: int = 2,
    ) -> int:
        """Generate a challenge, harvest a verified solution, and remember it.

        Returns the number of trajectories committed to active memory this call.
        """
        challenge = self._curriculum.run(domain, start=difficulty, rounds=rounds).value
        solution = self.llm.reason(f"Solve:\n{challenge.prompt}").text
        sample = self._harvester.harvest(challenge, solution)
        if sample is None:
            self.ledger.append("synthesize.unverified", domain=domain)
            return 0

        self.memory.remember(
            Trajectory(
                traj_id=f"traj-{len(self.memory) + 1}",
                domain=challenge.domain,
                problem=challenge.prompt,
                solution=sample.solution,
                reward=1.0,
                tags=(challenge.domain,),
            )
        )
        self.ledger.append("synthesize.remember", domain=challenge.domain)
        return 1

    # -- module A: synthesize a new capability ----------------------------

    def synthesize_capability(self, capability_gap: str) -> bool:
        """Synthesize, verify, and (if approved) register a new capability.

        Returns True if the capability was verified *and* registered. A verified
        but unapproved capability is retained as a proposal, not activated.
        """
        proposal = self._synthesizer.run(capability_gap).value
        if proposal is None or not proposal.verified:
            self.ledger.append("capability.unverified", gap=capability_gap)
            return False

        approved = self.approval.review(
            ActionRequest(
                kind="register_capability",
                summary=f"Register capability '{proposal.name}': {proposal.description}",
                reversible=True,
            )
        ) if self.config.gate_capability_registration else True
        if not approved:
            self.ledger.append("capability.blocked", name=proposal.name)
            return False

        self.registry.register(proposal)
        self.ledger.append("capability.registered", name=proposal.name)
        return True

    # -- self-healing ------------------------------------------------------

    def heal(self, tb_text: str, region: str) -> ValidationResult | None:
        """Diagnose a fault and stage a gated fix for ``region``.

        Rollback/retry is the caller's autonomous recovery path; this method
        only proposes and stages a *code* fix, which stays gated.
        """
        source = self.staging.state.get(region, "")
        proposal = self._recovery.run(tb_text, source).value
        if not proposal.has_fix:
            self.ledger.append("heal.no_fix", region=region, root_cause=proposal.root_cause)
            return None
        candidate = Candidate(
            candidate_id=f"heal-{region}",
            description=proposal.root_cause,
            code=proposal.patched_source,
            next_state={**self.staging.state, region: proposal.patched_source},
        )
        approved = self.approval.review(
            ActionRequest(
                kind="apply_patch",
                summary=f"Apply self-healing fix to '{region}': {proposal.root_cause}",
                reversible=True,
            )
        ) if self.config.gate_merges else True
        outcome = self.staging.promote(candidate, approved=approved)
        self.ledger.append("heal.promote", region=region, outcome=outcome.outcome.value)
        return outcome

    # -- full cycle --------------------------------------------------------

    def step(
        self,
        hot_paths: list[HotPath],
        *,
        suite: BenchmarkSuite | None = None,
        system: SystemFn | None = None,
        efficiency: float = 0.0,
        synthesize_domain: str | None = None,
    ) -> CycleReport:
        """Run one complete cycle of the matrix."""
        report = CycleReport(hot_paths=list(hot_paths))
        self.ledger.append("cycle.start", hot_paths=[h.region for h in hot_paths])

        for hot in hot_paths:
            evo = self.evolve(hot)
            report.evolutions.append(evo)
            status = evo.outcome.value if evo.outcome else "skipped"
            report.trace.append(f"evolve {hot.region}: {status}")

        if suite is not None and system is not None:
            report.evaluation = self.evaluate(suite, system, efficiency=efficiency)
            report.trace.append(
                f"evaluate: objective={report.evaluation.objective:.4f} "
                f"({report.evaluation.verdict.value}"
                f"{', rolled back' if report.evaluation.rolled_back else ''})"
            )

        if synthesize_domain is not None:
            remembered = self.synthesize(synthesize_domain)
            report.trajectories_remembered = remembered
            report.trace.append(f"synthesize: remembered {remembered} trajectory(ies)")

        report.ledger_verified = self.ledger.verify()
        self.ledger.append("cycle.end", ledger_verified=report.ledger_verified)
        report.trace.append(f"ledger integrity: {'ok' if report.ledger_verified else 'FAILED'}")
        return report
