"""Test doubles that stand in for the Anthropic SDK.

``FakeSDK`` mimics the ``messages.create`` surface the :class:`LLMClient` relies
on, returning canned responses. A tiny content-block shim reproduces the shape
``cogniprime.llm._normalize`` walks (objects with ``.type`` and ``.text``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class _Block:
    type: str
    text: str


@dataclass
class _Response:
    content: list[_Block]
    stop_reason: str = "end_turn"
    model: str = "claude-opus-4-8"


class _Messages:
    def __init__(self, responder: Callable[[dict[str, Any]], str]) -> None:
        self._responder = responder

    def create(self, **kwargs: Any) -> _Response:
        text = self._responder(kwargs)
        return _Response(content=[_Block(type="text", text=text)])


class FakeSDK:
    """A stand-in Anthropic client driven by a responder callback.

    The responder receives the full ``messages.create`` kwargs and returns the
    text CogniPrime should see. Inspect ``kwargs['output_config']`` to branch on
    whether a JSON schema was requested and return matching JSON.
    """

    def __init__(self, responder: Callable[[dict[str, Any]], str]) -> None:
        self.messages = _Messages(responder)
        self.calls: list[dict[str, Any]] = []

        # Wrap the responder to record calls for assertions.
        original = self.messages._responder

        def recording(kwargs: dict[str, Any]) -> str:
            self.calls.append(kwargs)
            return original(kwargs)

        self.messages._responder = recording
