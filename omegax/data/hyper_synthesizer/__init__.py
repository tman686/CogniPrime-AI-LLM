"""The Autonomous Knowledge & Synthesis Engine.

Generates increasingly hard reasoning/math/systems tasks (adversarial
curriculum), verifies synthetic outputs in a sandbox (formal verification
harvester), and persists solved trajectories into a queryable memory layer.
"""

from omegax.data.hyper_synthesizer.active_memory import (
    ActiveMemoryLayer,
    Trajectory,
    TrajectoryLink,
)
from omegax.data.hyper_synthesizer.curriculum import (
    Challenge,
    CurriculumGenerator,
    Difficulty,
)
from omegax.data.hyper_synthesizer.verification import (
    VerificationHarvester,
    VerifiedSample,
)

__all__ = [
    "ActiveMemoryLayer",
    "Trajectory",
    "TrajectoryLink",
    "Challenge",
    "CurriculumGenerator",
    "Difficulty",
    "VerificationHarvester",
    "VerifiedSample",
]
