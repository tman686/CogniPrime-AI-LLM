"""Thin, uniform wrapper around the Anthropic Messages API.

Every subsystem reasons through :class:`LLMClient`, so model selection,
adaptive thinking, effort, and structured-output handling live in exactly one
place. The client is deliberately small — it does not hide the SDK, it just
gives CogniPrime one consistent call shape.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from cogniprime.config import CogniPrimeConfig

try:  # pragma: no cover - import guard exercised only without the SDK installed
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]


@dataclass(slots=True)
class LLMResponse:
    """Normalized result of a reasoning call."""

    text: str
    stop_reason: str | None
    model: str

    def json(self) -> Any:
        """Parse the response text as JSON.

        Used with :meth:`LLMClient.structured` where the model is constrained to
        emit a JSON object matching a schema.
        """
        return json.loads(self.text)


class LLMClient:
    """Uniform reasoning interface backed by Claude.

    The client is instantiated lazily against the Anthropic SDK. Passing an
    explicit ``sdk_client`` (any object exposing ``messages.create``) makes the
    subsystems trivially testable without network access.
    """

    def __init__(self, config: CogniPrimeConfig, *, sdk_client: Any | None = None) -> None:
        self.config = config
        if sdk_client is not None:
            self._client = sdk_client
        else:
            if anthropic is None:  # pragma: no cover
                raise RuntimeError(
                    "The 'anthropic' package is required. Install it with "
                    "`pip install anthropic`, or pass a sdk_client for testing."
                )
            self._client = anthropic.Anthropic(api_key=config.api_key)

    def reason(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 8192,
        effort: str | None = None,
    ) -> LLMResponse:
        """Run a single reasoning turn with adaptive thinking enabled."""
        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": effort or self.config.effort},
            system=system or _DEFAULT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return _normalize(response, self.config.model)

    def structured(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        system: str | None = None,
        max_tokens: int = 8192,
        effort: str | None = None,
    ) -> LLMResponse:
        """Run a reasoning turn constrained to a JSON schema.

        Subsystems use this to get machine-readable plans (opportunity reports,
        diagnostics, patch descriptors) rather than parsing free text.
        """
        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={
                "effort": effort or self.config.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            system=system or _DEFAULT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return _normalize(response, self.config.model)


_DEFAULT_SYSTEM = (
    "You are a subsystem of CogniPrime, an autonomous Agentic-OS operating over "
    "a corporate ecosystem's code, infrastructure, and financial data. Be "
    "precise, evidence-based, and conservative: never claim work you cannot "
    "point to, and flag any action that is hard to reverse."
)


def _normalize(response: Any, model: str) -> LLMResponse:
    """Collapse a Messages API response into an :class:`LLMResponse`."""
    stop_reason = getattr(response, "stop_reason", None)
    text_parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    return LLMResponse(
        text="".join(text_parts),
        stop_reason=stop_reason,
        model=getattr(response, "model", model),
    )
