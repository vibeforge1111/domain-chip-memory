from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .contracts import AnswerCandidate, JsonDict, MemoryRole, NormalizedBenchmarkSample


@dataclass(frozen=True)
class RetrievedContextItem:
    session_id: str
    turn_ids: list[str]
    score: float
    strategy: str
    text: str
    memory_role: MemoryRole = "unknown"
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class BaselinePromptPacket:
    benchmark_name: str
    baseline_name: str
    sample_id: str
    question_id: str
    question: str
    assembled_context: str
    retrieved_context_items: list[RetrievedContextItem]
    metadata: JsonDict = field(default_factory=dict)
    answer_candidates: list[AnswerCandidate] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        return {
            "benchmark_name": self.benchmark_name,
            "baseline_name": self.baseline_name,
            "sample_id": self.sample_id,
            "question_id": self.question_id,
            "question": self.question,
            "assembled_context": self.assembled_context,
            "retrieved_context_items": [item.to_dict() for item in self.retrieved_context_items],
            "metadata": self.metadata,
            "answer_candidates": [candidate.to_dict() for candidate in self.answer_candidates],
        }


@dataclass(frozen=True)
class BenchmarkRunManifest:
    run_id: str
    benchmark_name: str
    baseline_name: str
    sample_ids: list[str]
    question_ids: list[str]
    question_count: int
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


def build_run_manifest(
    samples: list[NormalizedBenchmarkSample],
    *,
    baseline_name: str,
    run_id: str,
    benchmark_name: str | None = None,
    metadata: JsonDict | None = None,
) -> BenchmarkRunManifest:
    if benchmark_name:
        inferred_benchmark = benchmark_name
    else:
        benchmark_names = sorted({sample.benchmark_name for sample in samples})
        if not benchmark_names:
            inferred_benchmark = "unknown"
        elif len(benchmark_names) == 1:
            inferred_benchmark = benchmark_names[0]
        else:
            inferred_benchmark = "mixed"
    sample_ids = [sample.sample_id for sample in samples]
    question_ids = [question.question_id for sample in samples for question in sample.questions]
    derived_metadata: JsonDict = {}
    sample_source_formats = sorted(
        {
            str(sample.metadata.get("source_format", "")).strip()
            for sample in samples
            if str(sample.metadata.get("source_format", "")).strip()
        }
    )
    if sample_source_formats:
        derived_metadata["sample_source_formats"] = sample_source_formats
    if inferred_benchmark == "BEAM":
        source_modes = sorted(
            {
                str(sample.metadata.get("source_mode", "")).strip()
                for sample in samples
                if str(sample.metadata.get("source_mode", "")).strip()
            }
        )
        slice_statuses = sorted(
            {
                str(sample.metadata.get("slice_status", "")).strip()
                for sample in samples
                if str(sample.metadata.get("slice_status", "")).strip()
            }
        )
        dataset_scales = sorted(
            {
                str(sample.metadata.get("dataset_scale", "")).strip()
                for sample in samples
                if str(sample.metadata.get("dataset_scale", "")).strip()
            }
        )
        upstream_commits = sorted(
            {
                str(sample.metadata.get("upstream_commit", "")).strip()
                for sample in samples
                if str(sample.metadata.get("upstream_commit", "")).strip()
            }
        )
        if source_modes:
            derived_metadata["source_modes"] = source_modes
        if slice_statuses:
            derived_metadata["slice_statuses"] = slice_statuses
        if dataset_scales:
            derived_metadata["dataset_scales"] = dataset_scales
        if upstream_commits:
            derived_metadata["upstream_commits"] = upstream_commits
    return BenchmarkRunManifest(
        run_id=run_id,
        benchmark_name=inferred_benchmark,
        baseline_name=baseline_name,
        sample_ids=sample_ids,
        question_ids=question_ids,
        question_count=len(question_ids),
        metadata={**derived_metadata, **(metadata or {})},
    )
