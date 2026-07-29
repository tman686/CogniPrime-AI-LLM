"""Project Omega-X (SASM) — a recursive self-improvement matrix.

Omega-X extends the CogniPrime Agentic-OS with a bounded, auditable, and gated
recursive self-improvement loop, organized as five module groups:

* :mod:`omegax.core.hyper_evolution` — telemetry-driven self-rewriting,
  capability synthesis, and RLAIF/DPO preference optimization.
* :mod:`omegax.data.hyper_synthesizer` — adversarial curriculum, sandboxed
  formal verification, and vector + hypergraph active memory.
* :mod:`omegax.eval.supremacy` — benchmark harvesting, a supremacy objective,
  and a zero-tolerance regression shield with auto-rollback.
* :mod:`omegax.core.resilience` — chaos-engineering fault injection, a
  compliance-scoped distillation pipeline, and a cryptographic ledger.
* :mod:`omegax.sandbox` / :mod:`omegax.recovery` — atomic staging with
  sandbox verification, and self-healing recovery.

The :class:`~omegax.matrix.OmegaMatrix` runs one cycle of the whole loop. Every
irreversible self-modification is approval-gated and ledger-recorded; automated
rollback (restoring known-good state) is the only self-action that runs
ungated.
"""

from omegax.config import OmegaConfig
from omegax.frontier import FRONTIER_DIRECTIVE, CapabilityFrontier, seed_default_frontier
from omegax.matrix import CycleReport, OmegaMatrix

__all__ = [
    "OmegaConfig",
    "OmegaMatrix",
    "CycleReport",
    "CapabilityFrontier",
    "FRONTIER_DIRECTIVE",
    "seed_default_frontier",
]
