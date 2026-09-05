"""Base agent abstraction shared by every CogniPrime subsystem.

An :class:`Agent` is a named, reasoning unit with access to the shared
:class:`~cogniprime.llm.LLMClient`. Subsystems compose agents rather than
calling the LLM ad hoc, which keeps their behavior observable and auditable.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient

T = TypeVar("T")


@dataclass(slots=True)
class AgentResult(Generic[T]):
    """Outcome of an agent run, carrying both the value and an audit trail.

    The ``trace`` records human-readable steps so that any autonomous decision
    (a detected opportunity, a proposed patch) can be explained after the fact.
    """

    value: T
    trace: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def log(self, message: str) -> None:
        self.trace.append(message)


class Agent(abc.ABC, Generic[T]):
    """A named reasoning unit.

    Subclasses implement :meth:`run`. They should append to
    :class:`AgentResult.trace` as they work so that the orchestrator can surface
    a coherent narrative of what the Agentic-OS did and why.
    """

    #: Human-readable identifier used in traces and logs.
    name: str = "agent"

    def __init__(self, config: CogniPrimeConfig, llm: LLMClient) -> None:
        self.config = config
        self.llm = llm

    @abc.abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> AgentResult[T]:
        """Execute the agent and return its result with an audit trail."""
        raise NotImplementedError
