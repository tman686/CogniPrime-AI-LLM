"""Approval gates for hard-to-reverse, outward-facing actions.

CogniPrime is autonomous, but launching a venture, provisioning servers, and
patching production code are exactly the actions that must not run unchecked.
An :class:`ApprovalGate` decides whether a proposed action may proceed.

The default :class:`AutoDenyGate` denies everything, so an engine wired with
defaults will *plan* but never *act* — you opt into action explicitly by
supplying a gate (a human callback, a policy engine, or, in tests,
:class:`AutoApproveGate`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(slots=True, frozen=True)
class ActionRequest:
    """A proposed action awaiting an approval decision."""

    kind: str  # e.g. "launch_venture", "provision", "apply_patch"
    summary: str
    reversible: bool = False


class ApprovalGate(Protocol):
    """Decides whether a proposed action may proceed."""

    def review(self, request: ActionRequest) -> bool:
        """Return True to allow the action, False to block it."""
        ...


class AutoDenyGate:
    """Deny every action. The safe default for an unconfigured Agentic-OS."""

    def review(self, request: ActionRequest) -> bool:  # noqa: D102
        return False


class AutoApproveGate:
    """Approve every action. Intended for tests and fully-trusted automation."""

    def review(self, request: ActionRequest) -> bool:  # noqa: D102
        return True


@dataclass(slots=True)
class CallbackGate:
    """Delegate the decision to a user-supplied callable (e.g. a human prompt)."""

    callback: Callable[[ActionRequest], bool]

    def review(self, request: ActionRequest) -> bool:
        return self.callback(request)
