from domain_chip_memory.baselines import build_full_context_packets, build_lexical_packets
from domain_chip_memory.canonical_configs import get_canonical_configs
from domain_chip_memory.responders import heuristic_response
from domain_chip_memory.sample_data import demo_samples
from domain_chip_memory.scorecards import (
    BaselinePrediction,
    build_scorecard,
    build_scorecard_contract_summary,
    run_baseline_predictions,
)


def test_demo_scorecards_run_end_to_end():
    samples = demo_samples()

    full_manifest, full_packets = build_full_context_packets(samples)
    full_predictions = run_baseline_predictions(
        samples,
        full_packets,
        responder_name="heuristic_v1",
        responder=heuristic_response,
    )
    full_scorecard = build_scorecard(full_manifest, full_predictions)

    lexical_manifest, lexical_packets = build_lexical_packets(samples, top_k_sessions=1)
    lexical_predictions = run_baseline_predictions(
        samples,
        lexical_packets,
        responder_name="heuristic_v1",
        responder=heuristic_response,
    )
    lexical_scorecard = build_scorecard(lexical_manifest, lexical_predictions)

    assert full_scorecard["overall"]["total"] == 2
    assert lexical_scorecard["overall"]["total"] == 2
    assert full_scorecard["audited_overall"]["total"] == 2
    assert lexical_scorecard["audited_overall"]["total"] == 2
    assert full_scorecard["overall"]["accuracy"] >= 0.5
    assert lexical_scorecard["overall"]["accuracy"] >= 0.5


def test_scorecard_contract_and_canonical_config_exist():
    summary = build_scorecard_contract_summary()
    configs = get_canonical_configs()

    assert summary["scorecard_fields"]
    assert "benchmark_slices" in summary["scorecard_fields"]
    assert configs
    assert configs[0]["config_id"] == "benchmark-v3-32k.yml"


def test_build_scorecard_flags_known_benchmark_issues():
    scorecard = build_scorecard(
        {
            "run_id": "test-run",
            "benchmark_name": "LoCoMo",
            "baseline_name": "observational_temporal_memory",
            "sample_ids": ["conv-26"],
            "question_ids": ["conv-26-qa-6", "conv-26-qa-24"],
            "question_count": 2,
            "metadata": {},
        },
        [
            BaselinePrediction(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-6",
                category="2",
                predicted_answer="The saturday before 25 May 2023",
                expected_answers=["The sunday before 25 May 2023"],
                is_correct=False,
                metadata={"provider_name": "minimax:MiniMax-M2.7"},
            ),
            BaselinePrediction(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-24",
                category="1",
                predicted_answer="Charlotte's Web",
                expected_answers=['"Nothing is Impossible", "Charlotte\'s Web"'],
                is_correct=False,
                metadata={"provider_name": "minimax:MiniMax-M2.7"},
            ),
        ],
    )

    assert scorecard["known_issue_summary"]["total_flagged"] == 1
    assert scorecard["known_issue_summary"]["incorrect_flagged"] == 1
    assert scorecard["known_issue_summary"]["audit_excluded_total"] == 1
    assert scorecard["overall"]["accuracy"] == 0.0
    assert scorecard["audited_overall"]["total"] == 1
    assert scorecard["audited_overall"]["excluded"] == 1
    assert scorecard["audited_overall"]["accuracy"] == 0.0
    assert scorecard["audited_by_category"][1]["category"] == "2"
    assert scorecard["audited_by_category"][1]["excluded"] == 1
    assert scorecard["predictions"][0]["metadata"]["known_issue"]["classification"] == "benchmark_inconsistency"
    assert "known_issue" not in scorecard["predictions"][1]["metadata"]


def test_build_scorecard_emits_beam_benchmark_slices():
    scorecard = build_scorecard(
        {
            "run_id": "beam-run",
            "benchmark_name": "BEAM",
            "baseline_name": "observational_temporal_memory",
            "sample_ids": ["beam-1"],
            "question_ids": ["beam-1-q-1", "beam-1-q-2"],
            "question_count": 2,
            "metadata": {},
        },
        [
            BaselinePrediction(
                benchmark_name="BEAM",
                baseline_name="observational_temporal_memory",
                sample_id="beam-1",
                question_id="beam-1-q-1",
                category="episodic_memory",
                predicted_answer="Dubai",
                expected_answers=["Dubai"],
                is_correct=True,
                metadata={
                    "provider_name": "heuristic_v1",
                    "should_abstain": False,
                    "evidence_scope": "single_session",
                    "temporal_scope": "dated",
                },
            ),
            BaselinePrediction(
                benchmark_name="BEAM",
                baseline_name="observational_temporal_memory",
                sample_id="beam-1",
                question_id="beam-1-q-2",
                category="abstention",
                predicted_answer="unknown",
                expected_answers=["Information provided is not enough"],
                is_correct=False,
                metadata={
                    "provider_name": "heuristic_v1",
                    "should_abstain": True,
                    "evidence_scope": "multi_session",
                    "temporal_scope": "undated",
                },
            ),
        ],
    )

    assert scorecard["benchmark_slices"]["should_abstain"][0]["label"] == "abstain"
    assert scorecard["benchmark_slices"]["should_abstain"][1]["label"] == "answer"
    assert scorecard["benchmark_slices"]["evidence_scope"][0]["label"] == "multi_session"
    assert scorecard["benchmark_slices"]["evidence_scope"][1]["label"] == "single_session"
    assert scorecard["benchmark_slices"]["temporal_scope"][0]["label"] == "dated"
    assert scorecard["benchmark_slices"]["temporal_scope"][1]["label"] == "undated"
    assert scorecard["benchmark_slices"]["should_abstain"][1]["accuracy"] == 1.0
