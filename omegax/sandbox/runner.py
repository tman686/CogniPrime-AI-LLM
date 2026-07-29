"""Sandboxed verification runners.

Self-generated code and synthetic outputs must be verified in isolation before
they are trusted. Two runners are provided:

* :class:`InProcessValidator` — the **safe default**. It never executes
  candidate source; it runs a user-supplied pure validation function against the
  candidate's declared outputs. Use this for logic/proof checking where you
  control the check.
* :class:`SubprocessSandbox` — an **opt-in** baseline executor that runs a code
  snippet in an isolated Python subprocess with a wall-clock timeout and (on
  POSIX) CPU/memory limits, network left to the caller's environment policy.

Neither is a substitute for a hardened, air-gapped container in production — the
spec's "Absolute Isolation Containers" requirement is satisfied by running the
whole matrix inside such a container. These runners are the in-process gate.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol


@dataclass(slots=True)
class SandboxReport:
    """Outcome of running a candidate through a sandbox."""

    passed: bool
    detail: str
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class SandboxRunner(Protocol):
    """Verifies a candidate in isolation and reports pass/fail."""

    def verify(self, code: str) -> SandboxReport:
        """Verify ``code`` and return a :class:`SandboxReport`."""
        ...


@dataclass(slots=True)
class InProcessValidator:
    """Safe default: validate without executing candidate source.

    The ``check`` callable receives the candidate string and returns
    ``(passed, detail)``. Because it never ``exec``s the candidate, it is safe to
    run on untrusted, model-generated content.
    """

    check: Callable[[str], tuple[bool, str]]

    def verify(self, code: str) -> SandboxReport:
        passed, detail = self.check(code)
        return SandboxReport(passed=passed, detail=detail)


@dataclass(slots=True)
class SubprocessSandbox:
    """Opt-in baseline executor for Python snippets in an isolated subprocess.

    Runs ``python -I`` (isolated mode) on the candidate in a temp file with a
    wall-clock timeout. On POSIX, an optional preexec sets CPU-time and address-
    space limits. Executing model-generated code is inherently risky; only use
    this inside a hardened container, and prefer :class:`InProcessValidator`
    where a pure check suffices.
    """

    timeout_seconds: float = 5.0
    cpu_seconds: int | None = 2
    memory_mb: int | None = 256
    expect_returncode: int = 0
    _preexec_disabled: bool = field(default=False, repr=False)

    def verify(self, code: str) -> SandboxReport:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "candidate.py"
            script.write_text(code, encoding="utf-8")
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", str(script)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    cwd=tmp,
                    preexec_fn=self._limits(),  # noqa: PLW1509 - intentional resource capping
                )
            except subprocess.TimeoutExpired as exc:
                return SandboxReport(
                    passed=False,
                    detail=f"timed out after {self.timeout_seconds}s",
                    stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
                    stderr=exc.stderr or "" if isinstance(exc.stderr, str) else "",
                    timed_out=True,
                )
        passed = proc.returncode == self.expect_returncode
        return SandboxReport(
            passed=passed,
            detail=f"exit code {proc.returncode}",
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def _limits(self):  # pragma: no cover - platform dependent
        """Return a preexec_fn that caps CPU and memory on POSIX, else None."""
        if self._preexec_disabled or sys.platform == "win32":
            return None
        try:
            import resource
        except ImportError:
            return None

        cpu = self.cpu_seconds
        mem_bytes = self.memory_mb * 1024 * 1024 if self.memory_mb else None

        def _set_limits() -> None:
            if cpu is not None:
                resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            if mem_bytes is not None:
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

        return _set_limits
