"""Lifecycle hook dispatcher (PreToolUse / PostToolUse / Stop).

A real-time audit and control point around tool use. ``PreToolUse`` handlers
can **veto** a tool call (e.g. a shell sanitizer that blocks destructive
commands); ``PostToolUse`` handlers observe results (e.g. trigger a test run or
append to the audit log); ``Stop`` handlers run when a turn ends.

Handlers only *observe and gate* — they never silently rewrite the system's own
parameters. This is the honest, safe version of a lifecycle-hook integration:
oversight, not an autonomous self-modifying daemon.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable


class HookEvent(str, enum.Enum):
    """Points in the tool lifecycle where handlers can run."""

    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"


@dataclass(slots=True)
class ToolCall:
    """A tool invocation flowing through the lifecycle."""

    tool: str
    args: dict[str, object] = field(default_factory=dict)
    result: object = None


@dataclass(slots=True)
class HookResult:
    """Aggregate decision from the PreToolUse handlers."""

    allowed: bool
    reasons: list[str] = field(default_factory=list)


# A handler returns (allowed, reason). For POST/STOP, ``allowed`` is ignored.
Handler = Callable[[ToolCall], tuple[bool, str]]


class HookDispatcher:
    """Registers and runs lifecycle handlers, with PreToolUse veto power."""

    def __init__(self) -> None:
        self._handlers: dict[HookEvent, list[Handler]] = {e: [] for e in HookEvent}
        self.audit_log: list[str] = []

    def register(self, event: HookEvent, handler: Handler) -> None:
        self._handlers[event].append(handler)

    def pre_tool_use(self, call: ToolCall) -> HookResult:
        """Run PreToolUse handlers; deny the call if any handler vetoes it."""
        result = HookResult(allowed=True)
        for handler in self._handlers[HookEvent.PRE_TOOL_USE]:
            allowed, reason = handler(call)
            if not allowed:
                result.allowed = False
                result.reasons.append(reason)
        self.audit_log.append(
            f"PreToolUse {call.tool}: {'ALLOW' if result.allowed else 'DENY'} "
            f"{'; '.join(result.reasons)}".rstrip()
        )
        return result

    def post_tool_use(self, call: ToolCall) -> None:
        """Run PostToolUse handlers (observers; cannot veto after the fact)."""
        for handler in self._handlers[HookEvent.POST_TOOL_USE]:
            handler(call)
        self.audit_log.append(f"PostToolUse {call.tool}")

    def stop(self, call: ToolCall | None = None) -> None:
        """Run Stop handlers when a turn ends."""
        marker = ToolCall(tool="<stop>") if call is None else call
        for handler in self._handlers[HookEvent.STOP]:
            handler(marker)
        self.audit_log.append("Stop")


# -- ready-made guardrail handlers ----------------------------------------

# Shell fragments that a sanitizing PreToolUse handler refuses outright.
_DANGEROUS_PATTERNS = (
    "rm -rf /",
    "rm -rf ~",
    ":(){",  # fork bomb
    "mkfs",
    "dd if=",
    "> /dev/sd",
    "chmod -R 777 /",
)


def shell_sanitizer(call: ToolCall) -> tuple[bool, str]:
    """A PreToolUse handler that blocks obviously destructive shell commands."""
    if call.tool not in {"bash", "shell", "exec"}:
        return True, ""
    command = str(call.args.get("command", ""))
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in command:
            return False, f"blocked dangerous shell pattern: {pattern!r}"
    return True, ""


def secret_guard(call: ToolCall) -> tuple[bool, str]:
    """A PreToolUse handler that blocks reads of common secret files."""
    target = str(call.args.get("path", "")) + " " + str(call.args.get("command", ""))
    for needle in (".env", "id_rsa", "credentials", ".aws/", ".ssh/"):
        if needle in target:
            return False, f"blocked access to sensitive path: {needle!r}"
    return True, ""
