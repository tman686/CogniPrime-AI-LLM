"""Cross-Model Distillation Pipeline.

Ingests reasoning material from external sources and distills clean reasoning
paths into a local training corpus.

**Compliance scope.** This pipeline is deliberately limited to sources you are
permitted to learn from: public benchmarks, openly-licensed / open-weights
releases, and APIs whose terms allow it. Scraping a proprietary model's API
output to train a competing model typically violates that provider's terms of
service, so :class:`SourceKind.PROPRIETARY_API` is rejected by the ingestion
gate rather than processed. Respect each source's license and robots/ToS.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from cogniprime.config import CogniPrimeConfig
from cogniprime.llm import LLMClient


class SourceKind(str, enum.Enum):
    """Provenance of an ingested source, used to gate what may be distilled."""

    PUBLIC_BENCHMARK = "public_benchmark"
    OPEN_WEIGHTS = "open_weights"
    PERMITTED_API = "permitted_api"  # terms explicitly allow training use
    PROPRIETARY_API = "proprietary_api"  # NOT permitted — rejected by the gate


# Source kinds the pipeline is allowed to distill from.
_ALLOWED = {SourceKind.PUBLIC_BENCHMARK, SourceKind.OPEN_WEIGHTS, SourceKind.PERMITTED_API}


@dataclass(slots=True, frozen=True)
class SourceRecord:
    """A unit of external material offered for distillation."""

    source_id: str
    kind: SourceKind
    problem: str
    reference: str
    license: str = "unknown"


@dataclass(slots=True, frozen=True)
class DistilledSample:
    """A cleaned reasoning path ready for local training."""

    source_id: str
    problem: str
    reasoning: str
    answer: str


class DistillationError(RuntimeError):
    """Raised when a source is not permitted for distillation."""


class DistillationPipeline:
    """Distills reasoning paths from permitted external sources only."""

    def __init__(self, config: CogniPrimeConfig, llm: LLMClient) -> None:
        self.config = config
        self.llm = llm
        self._samples: list[DistilledSample] = []
        self._rejected: list[SourceRecord] = []

    def ingest(self, record: SourceRecord) -> DistilledSample:
        """Distill one permitted source into a training sample.

        Raises :class:`DistillationError` for disallowed provenance (e.g.
        proprietary-API scraping), recording the rejection for audit.
        """
        if record.kind not in _ALLOWED:
            self._rejected.append(record)
            raise DistillationError(
                f"source {record.source_id} of kind {record.kind.value} is not "
                "permitted for distillation (proprietary-API outputs may not be "
                "used to train competing models)"
            )

        reasoning = self.llm.reason(
            "Produce a clean, step-by-step reasoning path that arrives at the "
            "reference answer for this problem. Do not copy the source verbatim; "
            "reconstruct the reasoning.\n\n"
            f"Problem:\n{record.problem}\n\nReference answer:\n{record.reference}"
        ).text
        sample = DistilledSample(
            source_id=record.source_id,
            problem=record.problem,
            reasoning=reasoning,
            answer=record.reference,
        )
        self._samples.append(sample)
        return sample

    def ingest_many(self, records: list[SourceRecord]) -> list[DistilledSample]:
        """Distill every *permitted* record, skipping (recording) disallowed ones."""
        out: list[DistilledSample] = []
        for record in records:
            try:
                out.append(self.ingest(record))
            except DistillationError:
                continue
        return out

    @property
    def samples(self) -> list[DistilledSample]:
        return list(self._samples)

    @property
    def rejected(self) -> list[SourceRecord]:
        return list(self._rejected)
