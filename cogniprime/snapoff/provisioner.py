"""Infrastructure provisioning for the Snap-Off Engine.

Provisioning is where the Agentic-OS touches the real world, so it is the most
carefully gated step. The :class:`Provisioner` protocol defines the contract;
:class:`DryRunProvisioner` is the safe default — it plans and records what
*would* be created without contacting any provider.

A real deployment implements :class:`Provisioner` against a cloud/bare-metal
API. The Snap-Off Engine never provisions without an approved plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from cogniprime.snapoff.scaffolder import ServiceSpec


@dataclass(slots=True, frozen=True)
class ProvisionedResource:
    """A record of one provisioned (or planned) infrastructure resource."""

    resource_type: str  # e.g. "server", "database", "load_balancer"
    name: str
    region: str
    dry_run: bool


class Provisioner(Protocol):
    """Provision infrastructure for a generated service."""

    def plan(self, spec: ServiceSpec, *, region: str) -> list[ProvisionedResource]:
        """Return the resources that would be created for ``spec``."""
        ...

    def apply(self, plan: list[ProvisionedResource]) -> list[ProvisionedResource]:
        """Create the planned resources and return the created records."""
        ...


@dataclass(slots=True)
class DryRunProvisioner:
    """Default provisioner: plans resources but never creates anything.

    ``apply`` is a no-op that returns the plan unchanged (with ``dry_run`` still
    True), so wiring the engine end to end is always side-effect free until a
    real provisioner is supplied.
    """

    region: str = "us-east-1"
    applied: list[ProvisionedResource] = field(default_factory=list)

    def plan(self, spec: ServiceSpec, *, region: str) -> list[ProvisionedResource]:
        # A minimal, opinionated topology for a new venture service.
        base = spec.service_name.lower().replace(" ", "-")
        return [
            ProvisionedResource("server", f"{base}-app", region, dry_run=True),
            ProvisionedResource("database", f"{base}-db", region, dry_run=True),
            ProvisionedResource("load_balancer", f"{base}-lb", region, dry_run=True),
        ]

    def apply(self, plan: list[ProvisionedResource]) -> list[ProvisionedResource]:
        self.applied.extend(plan)
        return list(plan)
