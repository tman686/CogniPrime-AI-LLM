"""The Recursive Hyper-Evolution Core.

Telemetry-driven self-improvement: profile the running system, meta-reason over
the hot paths to propose optimizations, synthesize new capabilities, and run a
preference-optimization loop — all producing *proposals* that the staging
pipeline and approval gates decide whether to commit.
"""

from omegax.core.hyper_evolution.capability_synth import (
    CapabilityProposal,
    CapabilitySynthesizer,
    ToolRegistry,
)
from omegax.core.hyper_evolution.optimization_loop import (
    PreferenceOptimizer,
    PreferencePair,
    PreferenceRecord,
)
from omegax.core.hyper_evolution.source_rewriter import (
    RewriteProposal,
    SourceRewriter,
)
from omegax.core.hyper_evolution.telemetry import (
    HotPath,
    TelemetryProfiler,
    TelemetryReport,
    Trace,
)

__all__ = [
    "CapabilityProposal",
    "CapabilitySynthesizer",
    "ToolRegistry",
    "PreferenceOptimizer",
    "PreferencePair",
    "PreferenceRecord",
    "RewriteProposal",
    "SourceRewriter",
    "HotPath",
    "TelemetryProfiler",
    "TelemetryReport",
    "Trace",
]
