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
    assert payload["summary"]["resolved_missing_fact_query_count"] == 0
    assert payload["summary"]["unresolved_missing_fact_query_count"] == 0
    assert payload["summary"]["classification_counts"] == {"answered_with_kb_support": 1}
    comparison = payload["comparisons"][0]
    assert comparison["replay_source_evidence"] == {
        "has_source_evidence": True,
        "current_state_count": 1,
        "observation_count": 1,
    }
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
                    {
                        "conversation_id": "session:telegram:dm:spark-memory-regression-user-answered-timezone",
                        "session_id": "session:telegram:dm:spark-memory-regression-user-answered-timezone",
                        "metadata": {
                            "human_id": "human:telegram:answered-timezone",
                        },
                        "turns": [
                            {
                                "message_id": "req-write-timezone",
                                "role": "user",
                                "content": "My timezone is Asia/Dubai.",
                                "timestamp": "2026-04-12T00:03:00Z",
                                "metadata": {
                                    "source_event_type": "memory_write_requested",
                                    "operation": "update",
                                    "subject": "human:telegram:answered-timezone",
                                    "predicate": "profile.timezone",
                                    "value": "Asia/Dubai",
                                },
                            },
                            {
                                "message_id": "req-query-answered-timezone",
                                "role": "user",
                                "content": "What is my timezone?",
                                "timestamp": "2026-04-12T00:03:10Z",
                                "metadata": {
                                    "request_id": "req-query-answered-timezone",
                                    "source_event_type": "plugin_or_chip_influence_recorded",
                                    "predicate": "profile.timezone",
                                    "label": "timezone",
                                    "query_kind": "single_fact",
                                },
                            },
                            {
                                "message_id": "req-query-answered-timezone",
                                "role": "assistant",
                                "content": "Your timezone is Asia/Dubai.",
                                "timestamp": "2026-04-12T00:03:11Z",
                                "metadata": {
                                    "request_id": "req-query-answered-timezone",
                                    "source_event_type": "tool_result_received",
                                    "bridge_mode": "memory_profile_fact",
                                    "routing_decision": "memory_profile_fact_query",
                                    "predicate": "profile.timezone",
                                    "value_found": True,
                                    "evidence_summary": "status=memory_profile_fact predicate=profile.timezone value_found=yes",
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
    assert payload["summary"]["query_count"] == 3
    assert payload["summary"]["memory_only_answered"] == 1
    assert payload["summary"]["memory_plus_kb_answered"] == 1
    assert payload["summary"]["missing_fact_query_count"] == 2
    assert payload["summary"]["resolved_missing_fact_query_count"] == 0
    assert payload["summary"]["unresolved_missing_fact_query_count"] == 2
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
    assert payload["summary"]["missing_fact_source_coverage"] == {"without_replay_source_evidence": 2}
    assert payload["summary"]["source_backed_answered_counts_by_missing_predicate"] == {"profile.timezone": 1}
    assert payload["summary"]["source_backed_examples_by_missing_predicate"] == {
        "profile.timezone": [
            {
                "conversation_id": "session:telegram:dm:spark-memory-regression-user-answered-timezone",
                "question": "What is my timezone?",
                "answer": "Asia/Dubai",
                "scenario_bucket": "regression",
            }
        ]
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
    assert payload["summary"]["classification_counts"] == {
        "answered_without_kb_support": 1,
        "missing_fact_query": 2,
    }
    regression_comparison = payload["comparisons"][0]
    assert regression_comparison["scenario_bucket"] == "regression"
    assert regression_comparison["action_bucket"] == "regression_candidate"
    assert regression_comparison["replay_source_evidence"] == {
        "has_source_evidence": False,
        "current_state_count": 0,
        "observation_count": 0,
    }
    assert regression_comparison["value_found"] is False
    assert regression_comparison["memory_only"]["answer"] is None
    assert regression_comparison["memory_plus_kb"]["kb_page_exists"] is False
    assert regression_comparison["classification"] == "missing_fact_query"
    cleanroom_comparison = payload["comparisons"][1]
    assert cleanroom_comparison["scenario_bucket"] == "boundary_abstention_cleanroom"
    assert cleanroom_comparison["action_bucket"] == "expected_cleanroom_boundary"
    assert cleanroom_comparison["replay_source_evidence"] == {
        "has_source_evidence": False,
        "current_state_count": 0,
        "observation_count": 0,
    }
    assert cleanroom_comparison["classification"] == "missing_fact_query"
    answered_comparison = payload["comparisons"][2]
    assert answered_comparison["scenario_bucket"] == "regression"
    assert answered_comparison["replay_source_evidence"] == {
        "has_source_evidence": True,
        "current_state_count": 1,
        "observation_count": 1,
    }
    assert answered_comparison["classification"] == "answered_without_kb_support"


def test_build_spark_memory_kb_sourcing_slice_selects_missing_and_source_backed_examples(
    tmp_path: Path, monkeypatch
):
    intake_payload = {
        "normalization": {
            "normalized": {
                "source": "spark_builder_state_db",
                "writable_roles": ["user"],
                "conversations": [
                    {
                        "conversation_id": "missing-hack-actor",
                        "session_id": "missing-hack-actor",
                        "metadata": {"human_id": "human:telegram:missing-hack-actor"},
                        "turns": [],
                        "probes": [],
                    },
                    {
                        "conversation_id": "answered-hack-actor",
                        "session_id": "answered-hack-actor",
                        "metadata": {"human_id": "human:telegram:answered-hack-actor"},
                        "turns": [],
                        "probes": [],
                    },
                    {
                        "conversation_id": "missing-timezone",
                        "session_id": "missing-timezone",
                        "metadata": {"human_id": "human:telegram:missing-timezone"},
                        "turns": [],
                        "probes": [],
                    },
                    {
                        "conversation_id": "answered-timezone",
                        "session_id": "answered-timezone",
                        "metadata": {"human_id": "human:telegram:answered-timezone"},
                        "turns": [],
                        "probes": [],
                    },
                ],
            }
        },
        "compile_result": {"output_dir": str(tmp_path / "kb")},
    }
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps(intake_payload), encoding="utf-8")

    ablation_payload = {
        "input_file": str(intake_file),
        "summary": {
            "missing_fact_predicates": {
                "profile.hack_actor": 1,
                "profile.timezone": 1,
            },
            "missing_fact_examples_by_predicate": {
                "profile.hack_actor": [
                    {
                        "conversation_id": "missing-hack-actor",
                        "question": "Who hacked us?",
                        "label": "hack actor",
                        "evidence_summary": "status=memory_profile_fact predicate=profile.hack_actor value_found=no",
                    }
                ],
                "profile.timezone": [
                    {
                        "conversation_id": "missing-timezone",
                        "question": "What is my timezone?",
                        "label": "timezone",
                        "evidence_summary": "status=memory_profile_fact predicate=profile.timezone value_found=no",
                    }
                ],
            },
            "source_backed_answered_counts_by_missing_predicate": {
                "profile.hack_actor": 1,
                "profile.timezone": 1,
            },
            "source_backed_examples_by_missing_predicate": {
                "profile.hack_actor": [
                    {
                        "conversation_id": "answered-hack-actor",
                        "question": "Who hacked us?",
                        "answer": "North Korea",
                        "scenario_bucket": "regression",
                    }
                ],
                "profile.timezone": [
                    {
                        "conversation_id": "answered-timezone",
                        "question": "What is my timezone?",
                        "answer": "Asia/Dubai",
                        "scenario_bucket": "regression",
                    }
                ],
            },
        },
    }
    ablation_file = tmp_path / "ablation.json"
    output_file = tmp_path / "sourcing-slice.json"
    ablation_file.write_text(json.dumps(ablation_payload), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "build-spark-memory-kb-sourcing-slice",
            str(ablation_file),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["summary"] == {
        "predicate_count": 2,
        "selected_conversation_count": 4,
        "missing_from_source_count": 0,
        "selected_conversation_ids": [
            "missing-hack-actor",
            "answered-hack-actor",
            "missing-timezone",
            "answered-timezone",
        ],
        "missing_predicates": [
            "profile.hack_actor",
            "profile.timezone",
        ],
    }
    assert payload["predicate_targets"] == [
        {
            "predicate": "profile.hack_actor",
            "missing_query_count": 1,
            "source_backed_answered_count": 1,
            "missing_examples": [
                {
                    "conversation_id": "missing-hack-actor",
                    "question": "Who hacked us?",
                    "label": "hack actor",
                    "evidence_summary": "status=memory_profile_fact predicate=profile.hack_actor value_found=no",
                }
            ],
            "source_backed_examples": [
                {
                    "conversation_id": "answered-hack-actor",
                    "question": "Who hacked us?",
                    "answer": "North Korea",
                    "scenario_bucket": "regression",
                }
            ],
        },
        {
            "predicate": "profile.timezone",
            "missing_query_count": 1,
            "source_backed_answered_count": 1,
            "missing_examples": [
                {
                    "conversation_id": "missing-timezone",
                    "question": "What is my timezone?",
                    "label": "timezone",
                    "evidence_summary": "status=memory_profile_fact predicate=profile.timezone value_found=no",
                }
            ],
            "source_backed_examples": [
                {
                    "conversation_id": "answered-timezone",
                    "question": "What is my timezone?",
                    "answer": "Asia/Dubai",
                    "scenario_bucket": "regression",
                }
            ],
        },
    ]
    selected_ids = [
        item["conversation_id"]
        for item in payload["normalization"]["normalized"]["conversations"]
    ]
    assert selected_ids == [
        "missing-hack-actor",
        "answered-hack-actor",
        "missing-timezone",
        "answered-timezone",
    ]
    assert payload["compile_result"] == {"output_dir": str(tmp_path / "kb")}


def test_build_spark_memory_kb_source_backed_slice_injects_writes_and_clears_missing_query(
    tmp_path: Path, monkeypatch
):
    sourcing_slice_payload = {
        "predicate_targets": [
            {
                "predicate": "profile.timezone",
                "missing_query_count": 1,
                "source_backed_answered_count": 1,
                "missing_examples": [
                    {
                        "conversation_id": "missing-timezone",
                        "question": "What is my timezone?",
                        "label": "timezone",
                        "evidence_summary": "status=memory_profile_fact predicate=profile.timezone value_found=no",
                    }
                ],
                "source_backed_examples": [
                    {
                        "conversation_id": "answered-timezone",
                        "question": "What is my timezone?",
                        "answer": "Asia/Dubai",
                        "scenario_bucket": "regression",
                    }
                ],
            }
        ],
        "normalization": {
            "normalized": {
                "source": "spark_builder_state_db",
                "writable_roles": ["user"],
                "conversations": [
                    {
                        "conversation_id": "missing-timezone",
                        "session_id": "missing-timezone",
                        "metadata": {
                            "chat_id": "missing-timezone",
                            "human_id": "human:telegram:missing-timezone",
                        },
                        "turns": [
                            {
                                "message_id": "missing-query",
                                "role": "user",
                                "content": "What is my timezone?",
                                "timestamp": "2026-04-12T00:10:00Z",
                                "metadata": {
                                    "request_id": "missing-query",
                                    "source_event_type": "plugin_or_chip_influence_recorded",
                                    "predicate": "profile.timezone",
                                    "label": "timezone",
                                    "query_kind": "single_fact",
                                },
                            },
                            {
                                "message_id": "missing-query",
                                "role": "assistant",
                                "content": "Researcher bridge answered a single-fact profile query directly from memory.",
                                "timestamp": "2026-04-12T00:10:01Z",
                                "metadata": {
                                    "request_id": "missing-query",
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
                    {
                        "conversation_id": "answered-timezone",
                        "session_id": "answered-timezone",
                        "metadata": {
                            "chat_id": "answered-timezone",
                            "human_id": "human:telegram:answered-timezone",
                        },
                        "turns": [
                            {
                                "message_id": "write-timezone",
                                "role": "user",
                                "content": "My timezone is Asia/Dubai.",
                                "timestamp": "2026-04-12T00:00:00Z",
                                "metadata": {
                                    "request_id": "write-timezone",
                                    "source_event_type": "memory_write_requested",
                                    "operation": "update",
                                    "subject": "human:telegram:answered-timezone",
                                    "predicate": "profile.timezone",
                                    "value": "Asia/Dubai",
                                    "memory_kind": "observation",
                                },
                            },
                            {
                                "message_id": "answered-query",
                                "role": "user",
                                "content": "What is my timezone?",
                                "timestamp": "2026-04-12T00:00:05Z",
                                "metadata": {
                                    "request_id": "answered-query",
                                    "source_event_type": "plugin_or_chip_influence_recorded",
                                    "predicate": "profile.timezone",
                                    "label": "timezone",
                                    "query_kind": "single_fact",
                                },
                            },
                            {
                                "message_id": "answered-query",
                                "role": "assistant",
                                "content": "Your timezone is Asia/Dubai.",
                                "timestamp": "2026-04-12T00:00:06Z",
                                "metadata": {
                                    "request_id": "answered-query",
                                    "source_event_type": "tool_result_received",
                                    "bridge_mode": "memory_profile_fact",
                                    "routing_decision": "memory_profile_fact_query",
                                    "predicate": "profile.timezone",
                                    "value_found": True,
                                    "evidence_summary": "status=memory_profile_fact predicate=profile.timezone value_found=yes",
                                },
                            },
                        ],
                        "probes": [],
                    },
                ],
            }
        },
    }
    sourcing_slice_file = tmp_path / "sourcing-slice.json"
    output_dir = tmp_path / "source-backed-kb"
    output_file = tmp_path / "source-backed-slice.json"
    sourcing_slice_file.write_text(json.dumps(sourcing_slice_payload), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "build-spark-memory-kb-source-backed-slice",
            str(sourcing_slice_file),
            str(output_dir),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["summary"]["predicate_count"] == 1
    assert payload["summary"]["injected_write_count"] == 1
    assert payload["summary"]["target_conversation_count"] == 1
    assert payload["summary"]["missing_source_count"] == 0
    injected = payload["injected_writes"][0]
    assert injected["predicate"] == "profile.timezone"
    assert injected["target_conversation_id"] == "missing-timezone"
    injected_turn = payload["normalization"]["normalized"]["conversations"][0]["turns"][0]
    assert injected_turn["metadata"]["source_backed_clone"] is True
    assert injected_turn["metadata"]["subject"] == "human:telegram:missing-timezone"
    assert injected_turn["metadata"]["value"] == "Asia/Dubai"
    assert payload["compile_result"]["output_dir"] == str(output_dir)
    assert payload["health_report"]["valid"] is True

    ablation = cli._run_spark_memory_kb_ablation(str(output_file))
    assert ablation["summary"]["missing_fact_query_count"] == 1
    assert ablation["summary"]["resolved_missing_fact_query_count"] == 1
    assert ablation["summary"]["unresolved_missing_fact_query_count"] == 0
    assert ablation["summary"]["memory_only_answered"] == 2
    assert ablation["summary"]["memory_plus_kb_answered"] == 2
    assert ablation["summary"]["kb_supported_query_count"] == 2


def test_compare_spark_memory_kb_ablation_tracks_resolved_missing_queries(tmp_path: Path):
    before_payload = {
        "comparisons": [
            {
                "conversation_id": "missing-timezone",
                "request_id": "req-1",
                "predicate": "profile.timezone",
                "question": "What is my timezone?",
                "scenario_bucket": "boundary_abstention_cleanroom",
                "action_bucket": "expected_cleanroom_boundary",
                "value_found": False,
                "memory_only": {"found": False, "answer": None},
                "memory_plus_kb": {"found": False},
            },
            {
                "conversation_id": "answered-name",
                "request_id": "req-2",
                "predicate": "profile.preferred_name",
                "question": "What is my name?",
                "scenario_bucket": "regression",
                "action_bucket": "regression_candidate",
                "value_found": True,
                "memory_only": {"found": True, "answer": "Sarah"},
                "memory_plus_kb": {"found": True},
            },
        ]
    }
    after_payload = {
        "comparisons": [
            {
                "conversation_id": "missing-timezone",
                "request_id": "req-1",
                "predicate": "profile.timezone",
                "question": "What is my timezone?",
                "scenario_bucket": "boundary_abstention_cleanroom",
                "action_bucket": "expected_cleanroom_boundary",
                "value_found": False,
                "memory_only": {"found": True, "answer": "Asia/Dubai"},
                "memory_plus_kb": {"found": True},
            },
            {
                "conversation_id": "answered-name",
                "request_id": "req-2",
                "predicate": "profile.preferred_name",
                "question": "What is my name?",
                "scenario_bucket": "regression",
                "action_bucket": "regression_candidate",
                "value_found": True,
                "memory_only": {"found": True, "answer": "Sarah"},
                "memory_plus_kb": {"found": True},
            },
        ]
    }
    before_file = tmp_path / "before.json"
    after_file = tmp_path / "after.json"
    before_file.write_text(json.dumps(before_payload), encoding="utf-8")
    after_file.write_text(json.dumps(after_payload), encoding="utf-8")

    payload = cli._compare_spark_memory_kb_ablation(str(before_file), str(after_file))

    assert payload["summary"] == {
        "shared_query_count": 2,
        "before_only_query_count": 0,
        "after_only_query_count": 0,
        "transition_counts": {
            "not_missing_fact_query->not_missing_fact_query": 1,
            "unresolved_missing_fact_query->resolved_missing_fact_query": 1,
        },
        "resolved_missing_query_count": 1,
        "resolved_missing_by_predicate": {"profile.timezone": 1},
        "resolved_missing_by_scenario": {"boundary_abstention_cleanroom": 1},
        "resolved_missing_by_action_bucket": {"expected_cleanroom_boundary": 1},
        "still_unresolved_by_predicate": {},
    }
    assert payload["resolved_queries"] == [
        {
            "conversation_id": "missing-timezone",
            "question": "What is my timezone?",
            "predicate": "profile.timezone",
            "scenario_bucket": "boundary_abstention_cleanroom",
            "action_bucket": "expected_cleanroom_boundary",
            "answer": "Asia/Dubai",
        }
    ]
