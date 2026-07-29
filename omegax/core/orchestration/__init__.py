"""Autonomous Multi-Agent Orchestration & Memory.

Three primitives for coordinating work at scale, safely:

* **Sub-agent swarm** — bounded concurrent execution of many sub-tasks (real
  parallelism with a hard worker cap, not "hundreds of unbounded threads").
* **Lifecycle hooks** — a ``PreToolUse`` / ``PostToolUse`` / ``Stop`` dispatcher
  that audits and can *veto* tool calls in real time. ``PreToolUse`` handlers
  gate execution; they never silently self-modify the system.
* **Episodic memory** — persistent cross-session recall of task trajectories,
  successful debugging paths, and failed hypotheses.
"""

from omegax.core.orchestration.episodic_memory import Episode, EpisodicMemory
from omegax.core.orchestration.hooks import HookDispatcher, HookEvent, HookResult, ToolCall
from omegax.core.orchestration.red_team import (
    AdversarialProbe,
    ArbitrationResult,
    RedTeamArbitrator,
    Verdict,
)
from omegax.core.orchestration.swarm import SubAgentSwarm, SwarmResult, SwarmTask

__all__ = [
    "Episode",
    "EpisodicMemory",
    "HookDispatcher",
    "HookEvent",
    "HookResult",
    "ToolCall",
    "AdversarialProbe",
    "ArbitrationResult",
    "RedTeamArbitrator",
    "Verdict",
    "SubAgentSwarm",
    "SwarmResult",
    "SwarmTask",
]
