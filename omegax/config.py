"""Configuration for Project Omega-X (SASM).

Omega-X builds on the CogniPrime foundation (LLM client, agents, approval
gates) and adds the controls specific to a recursive self-improvement loop:
how many evolution cycles may run, and — critically — which self-modifications
require human sign-off before touching production.

The autonomy posture here is deliberate. A recursive self-improvement system
that merges its own code to production unreviewed is unsafe by construction, so
the irreversible steps (merging a rewrite, promoting to production, registering
a new capability) are gated by default. Automated *rollback* is not gated —
restoring a known-good state is always safe.
"""

from __future__ import annotations

from dataclasses import dataclass

from cogniprime.config import DEFAULT_MODEL, CogniPrimeConfig


@dataclass(slots=True)
class OmegaConfig:
    """Runtime configuration for the Omega-X matrix.

    Attributes:
        model: Claude model ID used for all meta-reasoning.
        effort: Default reasoning effort.
        max_evolution_cycles: Hard ceiling on recursive self-improvement steps
            per invocation of the matrix loop. Bounds runaway recursion.
        gate_merges: Require approval before merging a self-authored rewrite.
        gate_production_promotion: Require approval before promoting a staged
            build to the live production matrix.
        gate_capability_registration: Require approval before a synthesized tool
            or capability is registered for use.
        auto_rollback: Automatically roll back on regression (always safe).
        api_key: Anthropic API key; falls back to ANTHROPIC_API_KEY.
    """

    model: str = DEFAULT_MODEL
    effort: str = "high"
    max_evolution_cycles: int = 3
    gate_merges: bool = True
    gate_production_promotion: bool = True
    gate_capability_registration: bool = True
    auto_rollback: bool = True
    api_key: str | None = None

    def __post_init__(self) -> None:
        if self.max_evolution_cycles < 1:
            raise ValueError("max_evolution_cycles must be >= 1")

    def to_cogniprime(self, *, effort: str | None = None) -> CogniPrimeConfig:
        """Derive a CogniPrime config for the shared LLM client and agents.

        ``require_human_approval`` is set from whether *any* gate is active, so
        CogniPrime-layer agents observe the same posture as the Omega gates.
        """
        gated = self.gate_merges or self.gate_production_promotion or self.gate_capability_registration
        return CogniPrimeConfig(
            model=self.model,
            effort=effort or self.effort,
            max_recursion_depth=self.max_evolution_cycles,
            require_human_approval=gated,
            api_key=self.api_key,
        )
