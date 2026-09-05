"""CogniPrime Snap-Off Engine.

An automated venture-deployment pipeline: detect an operational bottleneck or
market opportunity, generate the software repositories and APIs it needs, and
provision the infrastructure to launch it — gated by approval for any
irreversible action.
"""

from cogniprime.snapoff.engine import SnapOffEngine, VentureLaunch
from cogniprime.snapoff.opportunity import Opportunity, OpportunityScanner
from cogniprime.snapoff.provisioner import (
    DryRunProvisioner,
    ProvisionedResource,
    Provisioner,
)
from cogniprime.snapoff.scaffolder import GeneratedRepo, RepoScaffolder, ServiceSpec

__all__ = [
    "SnapOffEngine",
    "VentureLaunch",
    "Opportunity",
    "OpportunityScanner",
    "DryRunProvisioner",
    "ProvisionedResource",
    "Provisioner",
    "GeneratedRepo",
    "RepoScaffolder",
    "ServiceSpec",
]
