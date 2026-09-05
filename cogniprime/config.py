"""Configuration for the CogniPrime Agentic-OS.

Configuration is intentionally declarative: a single :class:`CogniPrimeConfig`
object is threaded through every subsystem so that model choice, effort, and
safety gates are set once and observed everywhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Default to the latest and most capable Claude model. Adaptive thinking is
# enabled by every LLM call in cogniprime.llm; effort is tuned per subsystem.
DEFAULT_MODEL = "claude-opus-4-8"


@dataclass(slots=True)
class CogniPrimeConfig:
    """Runtime configuration shared across all subsystems.

    Attributes:
        model: Claude model ID used for all reasoning calls.
        effort: Default effort level (``low``/``medium``/``high``/``xhigh``/``max``).
        max_recursion_depth: Hard ceiling on the Infinite-Context recursive RAG
            loop, preventing runaway self-expansion.
        require_human_approval: When True, any outward or hard-to-reverse action
            (provisioning servers, applying patches, launching a venture) is
            gated behind an explicit approval step rather than executed.
        api_key: Anthropic API key. Falls back to ``ANTHROPIC_API_KEY``; may be
            ``None`` when a profile-based credential is configured.
    """

    model: str = DEFAULT_MODEL
    effort: str = "high"
    max_recursion_depth: int = 4
    require_human_approval: bool = True
    api_key: str | None = field(default=None)

    def __post_init__(self) -> None:
        if self.api_key is None:
            self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if self.max_recursion_depth < 1:
            raise ValueError("max_recursion_depth must be >= 1")
        valid_effort = {"low", "medium", "high", "xhigh", "max"}
        if self.effort not in valid_effort:
            raise ValueError(f"effort must be one of {sorted(valid_effort)}")

    def for_subsystem(self, *, effort: str | None = None) -> "CogniPrimeConfig":
        """Return a copy of this config with an overridden effort level.

        Subsystems that need a different intelligence/latency trade-off (e.g.
        the Self-Healing Compiler running at ``max`` on a live incident) derive
        a scoped config rather than mutating the shared one.
        """
        return CogniPrimeConfig(
            model=self.model,
            effort=effort or self.effort,
            max_recursion_depth=self.max_recursion_depth,
            require_human_approval=self.require_human_approval,
            api_key=self.api_key,
        )
