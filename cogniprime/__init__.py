"""CogniPrime — a recursive, self-healing Agentic-OS.

CogniPrime is organized as three cooperating subsystems, coordinated by a
top-level :class:`~cogniprime.orchestrator.CogniPrime` Agentic-OS:

* **Infinite-Context Core** (:mod:`cogniprime.core`) — a continuous recursive
  RAG loop that maps the corporate ecosystem, codebase, and financial layers
  into a shared, queryable context.
* **Snap-Off Engine** (:mod:`cogniprime.snapoff`) — detects operational
  bottlenecks and market opportunities, then scaffolds the repositories, APIs,
  and infrastructure needed to launch a new line of business.
* **Self-Healing Compiler** (:mod:`cogniprime.healing`) — monitors production
  code across holdings, diagnoses vulnerabilities and logic errors, and
  proposes patches before systems experience downtime.
"""

from cogniprime.config import CogniPrimeConfig
from cogniprime.orchestrator import CogniPrime

__version__ = "0.1.0"

__all__ = ["CogniPrime", "CogniPrimeConfig", "__version__"]
