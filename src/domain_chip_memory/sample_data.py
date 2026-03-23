from __future__ import annotations

from .contracts import (
    NormalizedBenchmarkSample,
    NormalizedQuestion,
    NormalizedSession,
    NormalizedTurn,
)


def demo_samples() -> list[NormalizedBenchmarkSample]:
    return [
        NormalizedBenchmarkSample(
            benchmark_name="LongMemEval",
            sample_id="demo-longmemeval-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2024-04-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in London."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Noted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2024-04-20",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="I moved to Dubai."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="demo-longmemeval-1:q1",
                    question="Where do I live now?",
                    category="knowledge-update",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="LoCoMo",
            sample_id="demo-locomo-1",
            sessions=[
                NormalizedSession(
                    session_id="session_1",
                    timestamp="2024-01-01",
                    turns=[
                        NormalizedTurn(turn_id="d1", speaker="Alice", text="I like jazz."),
                        NormalizedTurn(turn_id="d2", speaker="Bob", text="Cool."),
                    ],
                ),
                NormalizedSession(
                    session_id="session_2",
                    timestamp="2024-01-10",
                    turns=[
                        NormalizedTurn(turn_id="d3", speaker="Alice", text="I now prefer techno."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="demo-locomo-1:q1",
                    question="What music does Alice prefer now?",
                    category="temporal",
                    expected_answers=["techno"],
                    evidence_session_ids=["session_2"],
                    evidence_turn_ids=["d3"],
                )
            ],
        ),
    ]
