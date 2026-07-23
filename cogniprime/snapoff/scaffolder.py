"""Repository and API scaffolding for the Snap-Off Engine.

Given an :class:`~cogniprime.snapoff.opportunity.Opportunity`, the scaffolder
asks the model to design a minimal service — its API surface and the files that
implement it — and returns an in-memory :class:`GeneratedRepo`. Materializing
that repo to disk or a git host is a separate, gated step so that generation is
always safe and reviewable before anything is written.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cogniprime.agents.base import Agent, AgentResult
from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient
from cogniprime.snapoff.opportunity import Opportunity

_SERVICE_SCHEMA = {
    "type": "object",
    "properties": {
        "service_name": {"type": "string"},
        "description": {"type": "string"},
        "endpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "method": {"type": "string"},
                    "path": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["method", "path", "summary"],
                "additionalProperties": False,
            },
        },
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["service_name", "description", "endpoints", "files"],
    "additionalProperties": False,
}


@dataclass(slots=True, frozen=True)
class Endpoint:
    method: str
    path: str
    summary: str


@dataclass(slots=True)
class ServiceSpec:
    """The designed API surface for a new venture's service."""

    service_name: str
    description: str
    endpoints: list[Endpoint] = field(default_factory=list)


@dataclass(slots=True)
class GeneratedRepo:
    """An in-memory repository awaiting review before it is written anywhere."""

    spec: ServiceSpec
    files: dict[str, str] = field(default_factory=dict)

    def materialize(self, root: str | Path) -> list[Path]:
        """Write the generated files under ``root`` and return their paths.

        This is the one side-effecting method on the repo. Callers should only
        invoke it after the venture launch has been approved.
        """
        root_path = Path(root)
        written: list[Path] = []
        for rel_path, content in self.files.items():
            target = root_path / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(target)
        return written


class RepoScaffolder(Agent[GeneratedRepo]):
    """Design and generate a service repository for an opportunity."""

    name = "repo-scaffolder"

    def __init__(self, config: CogniPrimeConfig, llm: LLMClient) -> None:
        super().__init__(config, llm)

    def run(self, opportunity: Opportunity) -> AgentResult[GeneratedRepo]:
        prompt = (
            "Design a minimal, production-shaped microservice that captures this "
            "venture opportunity. Return its name, description, API endpoints, and "
            "the source files that implement it (keep it small but runnable).\n\n"
            f"Opportunity: {opportunity.title}\n"
            f"Rationale: {opportunity.rationale}\n"
            f"Kind: {opportunity.kind}"
        )
        response = self.llm.structured(prompt, schema=_SERVICE_SCHEMA)
        payload = response.json()

        spec = ServiceSpec(
            service_name=payload["service_name"],
            description=payload["description"],
            endpoints=[
                Endpoint(method=e["method"], path=e["path"], summary=e["summary"])
                for e in payload["endpoints"]
            ],
        )
        files = {f["path"]: f["content"] for f in payload["files"]}
        repo = GeneratedRepo(spec=spec, files=files)

        result: AgentResult[GeneratedRepo] = AgentResult(value=repo)
        result.log(
            f"scaffolded '{spec.service_name}' with {len(spec.endpoints)} endpoints "
            f"and {len(files)} files"
        )
        return result
