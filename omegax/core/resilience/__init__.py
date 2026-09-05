"""Fault-Tolerance, Chaos Engineering & Distillation.

Three resilience primitives:

* **Chaos injector** — deterministically injects faults (latency, memory
  pressure, corrupted context, exceptions) to probe robustness.
* **Distillation pipeline** — ingests *public/open* benchmark and open-weights
  sources and distills reasoning paths into a local training corpus. Scoped to
  permitted sources; it does not scrape proprietary model APIs.
* **Cryptographic ledger** — an append-only hash-chained record of every
  self-modification, giving tamper-evident lineage of the system's evolution.
"""

from omegax.core.resilience.chaos import (
    ChaosInjector,
    FaultKind,
    FaultResult,
)
from omegax.core.resilience.distillation import (
    DistillationPipeline,
    DistilledSample,
    SourceKind,
    SourceRecord,
)
from omegax.core.resilience.ledger import CryptographicLedger, LedgerEntry

__all__ = [
    "ChaosInjector",
    "FaultKind",
    "FaultResult",
    "DistillationPipeline",
    "DistilledSample",
    "SourceKind",
    "SourceRecord",
    "CryptographicLedger",
    "LedgerEntry",
]
