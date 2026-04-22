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
    assert "product_memory_summary" in summary["scorecard_fields"]
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


def test_build_scorecard_excludes_locomo_missing_gold_rows_from_audited_scoring():
    scorecard = build_scorecard(
        {
            "run_id": "locomo-missing-gold-run",
            "benchmark_name": "LoCoMo",
            "baseline_name": "summary_synthesis_memory",
            "sample_ids": ["conv-41"],
            "question_ids": ["conv-41-qa-401"],
            "question_count": 1,
            "metadata": {},
        },
        [
            BaselinePrediction(
                benchmark_name="LoCoMo",
                baseline_name="summary_synthesis_memory",
                sample_id="conv-41",
                question_id="conv-41-qa-401",
                category="5",
                predicted_answer="unknown",
                expected_answers=[],
                is_correct=False,
                metadata={"provider_name": "heuristic_v1", "gold_answer_missing": True},
            )
        ],
    )

    assert scorecard["overall"]["total"] == 1
    assert scorecard["overall"]["accuracy"] == 0.0
    assert scorecard["audited_overall"]["total"] == 0
    assert scorecard["audited_overall"]["excluded"] == 1
    assert scorecard["known_issue_summary"]["total_flagged"] == 1
    assert scorecard["known_issue_summary"]["audit_excluded_total"] == 1
    assert scorecard["predictions"][0]["metadata"]["known_issue"]["classification"] == "missing_gold_answer"


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


def test_build_scorecard_emits_product_memory_summary():
    scorecard = build_scorecard(
        {
            "run_id": "product-memory-run",
            "benchmark_name": "BEAM",
            "baseline_name": "observational_temporal_memory",
            "sample_ids": ["beam-1", "beam-2"],
            "question_ids": ["beam-1-q-1", "beam-2-q-1"],
            "question_count": 2,
            "metadata": {},
        },
        [
            BaselinePrediction(
                benchmark_name="BEAM",
                baseline_name="observational_temporal_memory",
                sample_id="beam-1",
                question_id="beam-1-q-1",
                category="current_state",
                predicted_answer="Dubai",
                expected_answers=["Dubai"],
                is_correct=True,
                metadata={
                    "provider_name": "openai:gpt-4.1-mini",
                    "latency_ms": 120.0,
                    "total_tokens": 42,
                    "answer_candidate_count": 1,
                    "primary_answer_candidate_type": "current_state",
                    "primary_answer_candidate_source": "current_state_memory",
                    "primary_answer_candidate_role": "current_state",
                    "expected_answer_candidate_source": "current_state_memory",
                    "retrieved_memory_role_counts": {"current_state": 1, "structured_evidence": 2},
                    "provenance_supported": True,
                    "should_abstain": False,
                },
            ),
            BaselinePrediction(
                benchmark_name="BEAM",
                baseline_name="observational_temporal_memory",
                sample_id="beam-2",
                question_id="beam-2-q-1",
                category="abstention",
                predicted_answer="unknown",
                expected_answers=["Information provided is not enough"],
                is_correct=True,
                metadata={
                    "provider_name": "heuristic_v1",
                    "latency_ms": 0.0,
                    "total_tokens": 0,
                    "answer_candidate_count": 0,
                    "expected_answer_candidate_source": "current_state_deletion",
                    "retrieved_memory_role_counts": {"episodic": 1},
                    "provenance_supported": False,
                    "should_abstain": True,
                },
            ),
        ],
    )

    product_summary = scorecard["product_memory_summary"]["measured_metrics"]

    assert product_summary["latency_ms"]["available"] == 2
    assert product_summary["latency_ms"]["mean"] == 60.0
    assert product_summary["total_tokens"]["max"] == 42.0
    assert product_summary["answer_candidate_support_rate"]["supported"] == 1
    assert product_summary["answer_candidate_support_rate"]["rate"] == 0.5
    assert product_summary["primary_answer_candidate_sources"]["supported"] == 1
    assert product_summary["primary_answer_candidate_sources"]["rows"] == [
        {"label": "current_state_memory", "count": 1}
    ]
    assert product_summary["primary_answer_candidate_source_alignment"]["aligned"] == 1
    assert product_summary["primary_answer_candidate_source_alignment"]["rate"] == 0.5
    assert product_summary["primary_answer_candidate_roles"]["rows"] == [
        {"label": "current_state", "count": 1}
    ]
    assert product_summary["primary_answer_candidate_types"]["rows"] == [
        {"label": "current_state", "count": 1}
    ]
    assert product_summary["retrieved_memory_roles"]["supported"] == 2
    assert product_summary["retrieved_memory_roles"]["rows"] == [
        {"label": "current_state", "count": 1},
        {"label": "episodic", "count": 1},
        {"label": "structured_evidence", "count": 1},
    ]
    assert product_summary["retrieved_memory_role_items"]["rows"] == [
        {"label": "current_state", "count": 1},
        {"label": "episodic", "count": 1},
        {"label": "structured_evidence", "count": 2},
    ]
    assert product_summary["provenance_support_rate"]["supported"] == 1
    assert product_summary["abstention_honesty"]["honest"] == 1
    assert product_summary["abstention_honesty"]["rate"] == 1.0
    assert product_summary["current_state_accuracy"]["accuracy"] == 1.0
    assert "memory_drift_rate" in scorecard["product_memory_summary"]["unmeasured_metrics"]


def test_build_scorecard_emits_product_memory_task_slices():
    scorecard = build_scorecard(
        {
            "run_id": "product-memory-run",
            "benchmark_name": "ProductMemory",
            "baseline_name": "observational_temporal_memory",
            "sample_ids": ["pm-1", "pm-2", "pm-3"],
            "question_ids": ["pm-1-q-1", "pm-2-q-1", "pm-3-q-1"],
            "question_count": 3,
            "metadata": {},
        },
        [
            BaselinePrediction(
                benchmark_name="ProductMemory",
                baseline_name="observational_temporal_memory",
                sample_id="pm-1",
                question_id="pm-1-q-1",
                category="current_state",
                predicted_answer="green",
                expected_answers=["green"],
                is_correct=True,
                metadata={
                    "product_memory_task": "correction",
                    "memory_operation": "update",
                    "memory_scope": "single_facet",
                },
            ),
            BaselinePrediction(
                benchmark_name="ProductMemory",
                baseline_name="observational_temporal_memory",
                sample_id="pm-2",
                question_id="pm-2-q-1",
                category="abstention",
                predicted_answer="Dubai",
                expected_answers=["Information provided is not enough"],
                is_correct=False,
                metadata={
                    "product_memory_task": "deletion",
                    "memory_operation": "delete_one_facet",
                    "memory_scope": "multi_facet",
                },
            ),
            BaselinePrediction(
                benchmark_name="ProductMemory",
                baseline_name="observational_temporal_memory",
                sample_id="pm-3",
                question_id="pm-3-q-1",
                category="current_state",
                predicted_answer="espresso",
                expected_answers=["espresso"],
                is_correct=True,
                metadata={
                    "product_memory_task": "stale_state_drift",
                    "memory_operation": "supersession",
                    "memory_scope": "single_facet",
                },
            ),
        ],
    )

    rows = scorecard["benchmark_slices"]["product_memory_task"]
    labels = [row["label"] for row in rows]
    assert labels == ["correction", "deletion", "stale_state_drift"]
    assert rows[0]["accuracy"] == 1.0
    assert rows[1]["accuracy"] == 0.0

    operation_rows = scorecard["benchmark_slices"]["memory_operation"]
    operation_labels = [row["label"] for row in operation_rows]
    assert operation_labels == ["delete_one_facet", "supersession", "update"]
    assert operation_rows[0]["accuracy"] == 0.0
    assert operation_rows[1]["accuracy"] == 1.0
    assert operation_rows[2]["accuracy"] == 1.0

    scope_rows = scorecard["benchmark_slices"]["memory_scope"]
    scope_labels = [row["label"] for row in scope_rows]
    assert scope_labels == ["multi_facet", "single_facet"]
    assert scope_rows[0]["accuracy"] == 0.0
    assert scope_rows[1]["accuracy"] == 1.0
