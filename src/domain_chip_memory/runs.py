from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .contracts import AnswerCandidate, JsonDict, NormalizedBenchmarkSample


@dataclass(frozen=True)
class RetrievedContextItem:
    session_id: str
    turn_ids: list[str]
    score: float
    strategy: str
    text: str
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
    return BenchmarkRunManifest(
        run_id=run_id,
        benchmark_name=inferred_benchmark,
        baseline_name=baseline_name,
        sample_ids=sample_ids,
        question_ids=question_ids,
        question_count=len(question_ids),
        metadata=metadata or {},
    )
