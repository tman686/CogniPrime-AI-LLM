"""Hardened sandboxing and atomic staging for Omega-X self-modification.

Every self-generated upgrade is promoted through a staging pipeline that
snapshots the current state, validates the candidate in isolation, and either
commits atomically or rolls back. Nothing reaches the live matrix without
passing this gate.
"""

from omegax.sandbox.staging import (
    Candidate,
    Snapshot,
    StageOutcome,
    StagingPipeline,
    ValidationResult,
)
from omegax.sandbox.runner import (
    InProcessValidator,
    SandboxReport,
    SandboxRunner,
    SubprocessSandbox,
)

__all__ = [
    "Candidate",
    "Snapshot",
    "StageOutcome",
    "StagingPipeline",
    "ValidationResult",
    "InProcessValidator",
    "SandboxReport",
    "SandboxRunner",
    "SubprocessSandbox",
]
