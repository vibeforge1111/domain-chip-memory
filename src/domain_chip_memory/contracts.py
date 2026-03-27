from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


JsonDict = dict[str, Any]
AnswerCandidateType = Literal[
    "generic",
    "exact_numeric",
    "currency",
    "date",
    "location",
    "preference",
    "current_state",
    "abstain",
]
AnswerCandidateSource = Literal[
    "unknown",
    "current_state_memory",
    "current_state_deletion",
    "evidence_memory",
    "belief_memory",
    "event_calendar",
    "aggregate_memory",
    "referential_ambiguity",
    "temporal_ambiguity",
    "temporal_atom_router",
]
MemoryRole = Literal[
    "unknown",
    "current_state",
    "state_deletion",
    "structured_evidence",
    "belief",
    "event",
    "aggregate",
    "ambiguity",
]


@dataclass(frozen=True)
class NormalizedTurn:
    turn_id: str
    speaker: str
    text: str
    timestamp: str | None = None
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedSession:
    session_id: str
    turns: list[NormalizedTurn]
    timestamp: str | None = None
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "turns": [turn.to_dict() for turn in self.turns],
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class NormalizedQuestion:
    question_id: str
    question: str
    category: str
    expected_answers: list[str]
    evidence_session_ids: list[str]
    evidence_turn_ids: list[str]
    question_date: str | None = None
    should_abstain: bool = False
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedBenchmarkSample:
    benchmark_name: str
    sample_id: str
    sessions: list[NormalizedSession]
    questions: list[NormalizedQuestion]
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "benchmark_name": self.benchmark_name,
            "sample_id": self.sample_id,
            "sessions": [session.to_dict() for session in self.sessions],
            "questions": [question.to_dict() for question in self.questions],
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class NormalizedBenchmarkConfig:
    benchmark_name: str
    config_id: str
    run_name: str
    dataset_family_names: list[str]
    memory_span_tokens: int | None = None
    dataset_examples: int | None = None
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class AnswerCandidate:
    text: str
    candidate_type: AnswerCandidateType = "generic"
    source: AnswerCandidateSource = "unknown"
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)
