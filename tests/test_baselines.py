from domain_chip_memory.baselines import (
    build_baseline_contract_summary,
    build_full_context_packets,
    build_lexical_packets,
)
from domain_chip_memory.contracts import (
    NormalizedBenchmarkSample,
    NormalizedQuestion,
    NormalizedSession,
    NormalizedTurn,
)


def _build_sample() -> NormalizedBenchmarkSample:
    return NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="sample-1",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="2024-01-01",
                turns=[
                    NormalizedTurn(turn_id="s1:t1", speaker="Alice", text="I like jazz."),
                    NormalizedTurn(turn_id="s1:t2", speaker="Bob", text="Cool."),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="2024-01-10",
                turns=[
                    NormalizedTurn(turn_id="s2:t1", speaker="Alice", text="I now prefer techno."),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q-1",
                question="What music does Alice prefer now?",
                category="temporal",
                expected_answers=["techno"],
                evidence_session_ids=["session_2"],
                evidence_turn_ids=["s2:t1"],
            )
        ],
    )


def test_full_context_baseline_includes_every_session():
    manifest, packets = build_full_context_packets([_build_sample()])

    assert manifest["baseline_name"] == "full_context"
    assert manifest["question_count"] == 1
    assert len(packets) == 1
    assert "session_1" in packets[0].assembled_context
    assert "session_2" in packets[0].assembled_context
    assert len(packets[0].retrieved_context_items) == 2


def test_lexical_baseline_prefers_more_relevant_session():
    manifest, packets = build_lexical_packets([_build_sample()], top_k_sessions=1)

    assert manifest["baseline_name"] == "lexical"
    assert len(packets) == 1
    assert packets[0].retrieved_context_items[0].session_id == "session_2"
    assert "techno" in packets[0].assembled_context


def test_baseline_contract_summary_lists_baselines():
    summary = build_baseline_contract_summary()

    assert summary["run_contracts"]
    assert len(summary["baselines"]) == 2
