"""The Snap-Off Engine: opportunity -> repository -> infrastructure -> launch.

The engine strings together the scanner, scaffolder, and provisioner into a
single pipeline. Generation (scanning, designing, planning) always runs; the
irreversible steps (provisioning, marking a venture launched) run only when the
:class:`~cogniprime.approval.ApprovalGate` approves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cogniprime.approval import ActionRequest, ApprovalGate, AutoDenyGate
from cogniprime.config import CogniPrimeConfig
from cogniprime.core.context_core import ContextCore
from cogniprime.llm import LLMClient
from cogniprime.snapoff.opportunity import Opportunity, OpportunityScanner
from cogniprime.snapoff.provisioner import (
    DryRunProvisioner,
    ProvisionedResource,
    Provisioner,
)
from cogniprime.snapoff.scaffolder import GeneratedRepo, RepoScaffolder


@dataclass(slots=True)
class VentureLaunch:
    """The full record of a (planned or launched) venture spin-off."""

    opportunity: Opportunity
    repo: GeneratedRepo
    infrastructure: list[ProvisionedResource] = field(default_factory=list)
    launched: bool = False
    trace: list[str] = field(default_factory=list)


class SnapOffEngine:
    """Detects, builds, and (with approval) launches new lines of business."""

    def __init__(
        self,
        config: CogniPrimeConfig,
        llm: LLMClient,
        context: ContextCore,
        *,
        provisioner: Provisioner | None = None,
        approval: ApprovalGate | None = None,
    ) -> None:
        self.config = config
        self.llm = llm
        self.context = context
        self.provisioner: Provisioner = provisioner or DryRunProvisioner()
        self.approval: ApprovalGate = approval or AutoDenyGate()
        self._scanner = OpportunityScanner(config, llm, context)
        self._scaffolder = RepoScaffolder(config, llm)

    def scan(self) -> list[Opportunity]:
        """Detect venture opportunities, ranked by expected value."""
        return self._scanner.run().value

    def launch_best(self, *, region: str = "us-east-1") -> VentureLaunch | None:
        """Run the full pipeline for the highest-priority opportunity.

        Returns ``None`` when no opportunity is found. The returned
        :class:`VentureLaunch` always contains the generated repo and the
        *planned* infrastructure; ``launched`` and applied infrastructure depend
        on the approval gate.
        """
        opportunities = self.scan()
        if not opportunities:
            return None
        return self.launch(opportunities[0], region=region)

    def launch(self, opportunity: Opportunity, *, region: str = "us-east-1") -> VentureLaunch:
        """Build and, if approved, launch a single opportunity."""
        repo_result = self._scaffolder.run(opportunity)
        launch = VentureLaunch(opportunity=opportunity, repo=repo_result.value)
        launch.trace.extend(repo_result.trace)

        plan = self.provisioner.plan(repo_result.value.spec, region=region)
        launch.trace.append(f"planned {len(plan)} infrastructure resources in {region}")

        request = ActionRequest(
            kind="launch_venture",
            summary=(
                f"Launch venture '{opportunity.title}' "
                f"(service '{repo_result.value.spec.service_name}', "
                f"{len(plan)} resources in {region})"
            ),
            reversible=False,
        )
        if self.config.require_human_approval and not self.approval.review(request):
            launch.trace.append("approval denied: infrastructure not provisioned, venture not launched")
            return launch

        launch.infrastructure = self.provisioner.apply(plan)
        launch.launched = True
        launch.trace.append(f"launched venture with {len(launch.infrastructure)} resources")
        return launch
