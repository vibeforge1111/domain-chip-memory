from __future__ import annotations

import json
import sys
from pathlib import Path

from domain_chip_memory import cli
from domain_chip_memory.spark_kb import scaffold_spark_knowledge_base


def test_run_spark_memory_kb_ablation_reports_matching_answer_and_kb_support(tmp_path: Path, monkeypatch):
    kb_dir = tmp_path / "kb"
    snapshot = {
        "generated_at": "2026-04-12T00:00:00Z",
        "counts": {
            "session_count": 1,
            "current_state_count": 1,
            "observation_count": 1,
            "event_count": 0,
        },
        "sessions": [],
        "current_state": [
            {
                "memory_role": "current_state",
                "subject": "human:telegram:12345",
                "predicate": "profile.city",
                "text": "I live in Dubai.",
                "session_id": "session:telegram:dm:12345",
                "turn_ids": ["req-write"],
                "timestamp": "2026-04-12T00:00:00Z",
                "metadata": {"value": "Dubai", "observation_id": "obs-city-1"},
            }
        ],
        "observations": [
            {
                "memory_role": "current_state",
                "subject": "human:telegram:12345",
                "predicate": "profile.city",
                "text": "I live in Dubai.",
                "session_id": "session:telegram:dm:12345",
                "turn_ids": ["req-write"],
                "timestamp": "2026-04-12T00:00:00Z",
                "metadata": {"value": "Dubai", "observation_id": "obs-city-1"},
            }
        ],
        "events": [],
        "trace": {"operation": "export_knowledge_base_snapshot"},
    }
    scaffold_spark_knowledge_base(kb_dir, snapshot)

    intake_payload = {
        "normalization": {
            "normalized": {
                "source": "spark_builder_state_db",
                "writable_roles": ["user"],
                "conversations": [
                    {
                        "conversation_id": "session:telegram:dm:12345",
                        "session_id": "session:telegram:dm:12345",
                        "metadata": {
                            "human_id": "human:telegram:12345",
                        },
                        "turns": [
                            {
                                "message_id": "req-write",
                                "role": "user",
                                "content": "I live in Dubai.",
                                "timestamp": "2026-04-12T00:00:00Z",
                                "metadata": {
                                    "source_event_type": "memory_write_requested",
                                    "operation": "update",
                                    "subject": "human:telegram:12345",
                                    "predicate": "profile.city",
                                    "value": "Dubai",
                                },
                            },
                            {
                                "message_id": "req-query",
                                "role": "user",
                                "content": "Where do I live?",
                                "timestamp": "2026-04-12T00:01:00Z",
                                "metadata": {
                                    "request_id": "req-query",
                                    "source_event_type": "plugin_or_chip_influence_recorded",
                                    "predicate": "profile.city",
                                    "label": "city",
                                    "query_kind": "single_fact",
                                },
                            },
                            {
                                "message_id": "req-query",
                                "role": "assistant",
                                "content": "You live in Dubai.",
                                "timestamp": "2026-04-12T00:01:01Z",
                                "metadata": {
                                    "request_id": "req-query",
                                    "source_event_type": "tool_result_received",
                                    "bridge_mode": "memory_profile_fact",
                                    "routing_decision": "memory_profile_fact_query",
                                    "predicate": "profile.city",
                                    "value_found": True,
                                    "evidence_summary": "status=memory_profile_fact predicate=profile.city value_found=yes",
                                },
                            },
                        ],
                        "probes": [],
                    }
                ],
            }
        },
        "compile_result": {"output_dir": str(kb_dir)},
    }
    data_file = tmp_path / "intake.json"
    output_file = tmp_path / "ablation.json"
    data_file.write_text(json.dumps(intake_payload), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-spark-memory-kb-ablation",
            str(data_file),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["summary"]["query_count"] == 1
    assert payload["summary"]["memory_only_answered"] == 1
    assert payload["summary"]["memory_plus_kb_answered"] == 1
    assert payload["summary"]["answer_delta_count"] == 0
    assert payload["summary"]["kb_supported_query_count"] == 1
    assert payload["summary"]["classification_counts"] == {"answered_with_kb_support": 1}
    comparison = payload["comparisons"][0]
    assert comparison["memory_only"]["answer"] == "Dubai"
    assert comparison["memory_plus_kb"]["answer"] == "Dubai"
    assert comparison["memory_plus_kb"]["supporting_evidence_count"] == 1
    assert comparison["classification"] == "answered_with_kb_support"


def test_run_spark_memory_kb_ablation_tracks_missing_fact_queries(tmp_path: Path, monkeypatch):
    kb_dir = tmp_path / "kb-missing"
    scaffold_spark_knowledge_base(
        kb_dir,
        {
            "generated_at": "2026-04-12T00:00:00Z",
            "counts": {
                "session_count": 1,
                "current_state_count": 0,
                "observation_count": 0,
                "event_count": 0,
            },
            "sessions": [],
            "current_state": [],
            "observations": [],
            "events": [],
            "trace": {"operation": "export_knowledge_base_snapshot"},
        },
    )

    intake_payload = {
        "normalization": {
            "normalized": {
                "source": "spark_builder_state_db",
                "writable_roles": ["user"],
                "conversations": [
                    {
                        "conversation_id": "session:telegram:dm:spark-memory-regression-user-2c339238-hack_actor_query_missing",
                        "session_id": "session:telegram:dm:spark-memory-regression-user-2c339238-hack_actor_query_missing",
                        "metadata": {
                            "human_id": "human:telegram:missing-regression",
                        },
                        "turns": [
                            {
                                "message_id": "req-query",
                                "role": "user",
                                "content": "Who hacked us?",
                                "timestamp": "2026-04-12T00:01:00Z",
                                "metadata": {
                                    "request_id": "req-query",
                                    "source_event_type": "plugin_or_chip_influence_recorded",
                                    "predicate": "profile.hack_actor",
                                    "label": "hack actor",
                                    "query_kind": "single_fact",
                                },
                            },
                            {
                                "message_id": "req-query",
                                "role": "assistant",
                                "content": "Researcher bridge answered a single-fact profile query directly from memory.",
                                "timestamp": "2026-04-12T00:01:01Z",
                                "metadata": {
                                    "request_id": "req-query",
                                    "source_event_type": "tool_result_received",
                                    "bridge_mode": "memory_profile_fact",
                                    "routing_decision": "memory_profile_fact_query",
                                    "predicate": "profile.hack_actor",
                                    "value_found": False,
                                    "evidence_summary": "status=memory_profile_fact predicate=profile.hack_actor value_found=no",
                                },
                            },
                        ],
                        "probes": [],
                    },
                    {
                        "conversation_id": "session:telegram:dm:spark-memory-soak-user-ed0c3cbc-boundary_abstention-0005-timezone_query_missing_cleanroom",
                        "session_id": "session:telegram:dm:spark-memory-soak-user-ed0c3cbc-boundary_abstention-0005-timezone_query_missing_cleanroom",
                        "metadata": {
                            "human_id": "human:telegram:missing-cleanroom",
                        },
                        "turns": [
                            {
                                "message_id": "req-query-cleanroom",
                                "role": "user",
                                "content": "What is my timezone?",
                                "timestamp": "2026-04-12T00:02:00Z",
                                "metadata": {
                                    "request_id": "req-query-cleanroom",
                                    "source_event_type": "plugin_or_chip_influence_recorded",
                                    "predicate": "profile.timezone",
                                    "label": "timezone",
                                    "query_kind": "single_fact",
                                },
                            },
                            {
                                "message_id": "req-query-cleanroom",
                                "role": "assistant",
                                "content": "Researcher bridge answered a single-fact profile query directly from memory.",
                                "timestamp": "2026-04-12T00:02:01Z",
                                "metadata": {
                                    "request_id": "req-query-cleanroom",
                                    "source_event_type": "tool_result_received",
                                    "bridge_mode": "memory_profile_fact",
                                    "routing_decision": "memory_profile_fact_query",
                                    "predicate": "profile.timezone",
                                    "value_found": False,
                                    "evidence_summary": "status=memory_profile_fact predicate=profile.timezone value_found=no",
                                },
                            },
                        ],
                        "probes": [],
                    },
                ],
            }
        },
        "compile_result": {"output_dir": str(kb_dir)},
    }
    data_file = tmp_path / "missing-intake.json"
    output_file = tmp_path / "missing-ablation.json"
    data_file.write_text(json.dumps(intake_payload), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-spark-memory-kb-ablation",
            str(data_file),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["summary"]["query_count"] == 2
    assert payload["summary"]["memory_only_answered"] == 0
    assert payload["summary"]["memory_plus_kb_answered"] == 0
    assert payload["summary"]["missing_fact_query_count"] == 2
    assert payload["summary"]["missing_fact_predicates"] == {
        "profile.hack_actor": 1,
        "profile.timezone": 1,
    }
    assert payload["summary"]["missing_fact_scenarios"] == {
        "boundary_abstention_cleanroom": 1,
        "regression": 1,
    }
    assert payload["summary"]["missing_fact_predicates_by_scenario"] == {
        "boundary_abstention_cleanroom": {"profile.timezone": 1},
        "regression": {"profile.hack_actor": 1},
    }
    assert payload["summary"]["missing_fact_action_buckets"] == {
        "expected_cleanroom_boundary": 1,
        "regression_candidate": 1,
    }
    assert payload["summary"]["missing_fact_predicates_by_action_bucket"] == {
        "expected_cleanroom_boundary": {"profile.timezone": 1},
        "regression_candidate": {"profile.hack_actor": 1},
    }
    assert payload["summary"]["missing_fact_examples_by_predicate"] == {
        "profile.hack_actor": [
            {
                "conversation_id": "session:telegram:dm:spark-memory-regression-user-2c339238-hack_actor_query_missing",
                "question": "Who hacked us?",
                "label": "hack actor",
                "evidence_summary": "status=memory_profile_fact predicate=profile.hack_actor value_found=no",
            }
        ],
        "profile.timezone": [
            {
                "conversation_id": "session:telegram:dm:spark-memory-soak-user-ed0c3cbc-boundary_abstention-0005-timezone_query_missing_cleanroom",
                "question": "What is my timezone?",
                "label": "timezone",
                "evidence_summary": "status=memory_profile_fact predicate=profile.timezone value_found=no",
            }
        ]
    }
    assert payload["summary"]["classification_counts"] == {"missing_fact_query": 2}
    regression_comparison = payload["comparisons"][0]
    assert regression_comparison["scenario_bucket"] == "regression"
    assert regression_comparison["action_bucket"] == "regression_candidate"
    assert regression_comparison["value_found"] is False
    assert regression_comparison["memory_only"]["answer"] is None
    assert regression_comparison["memory_plus_kb"]["kb_page_exists"] is False
    assert regression_comparison["classification"] == "missing_fact_query"
    cleanroom_comparison = payload["comparisons"][1]
    assert cleanroom_comparison["scenario_bucket"] == "boundary_abstention_cleanroom"
    assert cleanroom_comparison["action_bucket"] == "expected_cleanroom_boundary"
    assert cleanroom_comparison["classification"] == "missing_fact_query"
