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


def test_run_spark_memory_kb_ablation_surfaces_policy_gated_runtime_vs_kb_divergence(
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

    source_backed_payload = json.loads(output_file.read_text(encoding="utf-8"))
    injected = source_backed_payload["injected_writes"][0]
    policy_payload = {
        "allowed_promotions": [],
        "deferred_promotions": [],
        "blocked_promotions": [
            {
                "policy_decision": "block",
                "action_bucket": "expected_cleanroom_boundary",
                "verdict": "retain_boundary_by_default",
                "recommendation": "keep boundary",
                "target_conversation_id": injected["target_conversation_id"],
                "predicate": injected["predicate"],
                "question": "What is my timezone?",
                "answer": "Asia/Dubai",
                "source_conversation_id": injected["source_conversation_id"],
                "source_message_id": injected["source_message_id"],
                "cloned_message_id": injected["cloned_message_id"],
                "value": injected["value"],
            }
        ],
    }
    policy_file = tmp_path / "promotion-policy.json"
    policy_file.write_text(json.dumps(policy_payload), encoding="utf-8")

    ablation = cli._run_spark_memory_kb_ablation(
        str(output_file),
        promotion_policy_file=str(policy_file),
    )

    assert ablation["summary"]["query_count"] == 2
    assert ablation["summary"]["memory_only_answered"] == 1
    assert ablation["summary"]["memory_plus_kb_answered"] == 2
    assert ablation["summary"]["answer_delta_count"] == 1
    assert ablation["summary"]["missing_fact_query_count"] == 1
    assert ablation["summary"]["resolved_missing_fact_query_count"] == 1
    assert ablation["trace"]["promotion_policy_file"] == str(policy_file)
    missing_row = next(
        item for item in ablation["comparisons"] if item["conversation_id"] == "missing-timezone"
    )
    assert missing_row["memory_only"]["found"] is False
    assert missing_row["memory_plus_kb"]["found"] is True
    assert missing_row["delta"]["answer_changed"] is True


def test_run_spark_memory_kb_ablation_can_recompile_policy_aligned_kb(
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

    source_backed_payload = json.loads(output_file.read_text(encoding="utf-8"))
    injected = source_backed_payload["injected_writes"][0]
    policy_payload = {
        "allowed_promotions": [],
        "deferred_promotions": [],
        "blocked_promotions": [
            {
                "policy_decision": "block",
                "action_bucket": "expected_cleanroom_boundary",
                "verdict": "retain_boundary_by_default",
                "recommendation": "keep boundary",
                "target_conversation_id": injected["target_conversation_id"],
                "predicate": injected["predicate"],
                "question": "What is my timezone?",
                "answer": "Asia/Dubai",
                "source_conversation_id": injected["source_conversation_id"],
                "source_message_id": injected["source_message_id"],
                "cloned_message_id": injected["cloned_message_id"],
                "value": injected["value"],
            }
        ],
    }
    policy_file = tmp_path / "promotion-policy.json"
    policy_file.write_text(json.dumps(policy_payload), encoding="utf-8")
    aligned_kb_dir = tmp_path / "policy-aligned-kb"

    ablation = cli._run_spark_memory_kb_ablation(
        str(output_file),
        promotion_policy_file=str(policy_file),
        recompile_kb_output_dir=str(aligned_kb_dir),
    )

    assert ablation["summary"]["query_count"] == 2
    assert ablation["summary"]["memory_only_answered"] == 1
    assert ablation["summary"]["memory_plus_kb_answered"] == 1
    assert ablation["summary"]["answer_delta_count"] == 0
    assert ablation["summary"]["missing_fact_query_count"] == 1
    assert ablation["summary"]["resolved_missing_fact_query_count"] == 0
    assert ablation["summary"]["unresolved_missing_fact_query_count"] == 1
    assert ablation["trace"]["promotion_policy_file"] == str(policy_file)
    assert ablation["trace"]["recompile_kb_output_dir"] == str(aligned_kb_dir)
    assert ablation["trace"]["kb_source"] == "recompiled_from_replay_snapshot"
    assert ablation["compile_result"]["output_dir"] == str(aligned_kb_dir)
    missing_row = next(
        item for item in ablation["comparisons"] if item["conversation_id"] == "missing-timezone"
    )
    assert missing_row["memory_only"]["found"] is False
    assert missing_row["memory_plus_kb"]["found"] is False
    assert missing_row["delta"]["answer_changed"] is False


def test_build_spark_memory_kb_policy_aligned_slice_compiles_governed_snapshot(tmp_path: Path):
    source_backed_slice_payload = {
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
                                "message_id": "clone-timezone",
                                "role": "user",
                                "content": "My timezone is Asia/Dubai.",
                                "timestamp": "2026-04-12T00:09:59Z",
                                "metadata": {
                                    "request_id": "clone-timezone",
                                    "source_event_type": "memory_write_requested",
                                    "operation": "update",
                                    "subject": "human:telegram:missing-timezone",
                                    "predicate": "profile.timezone",
                                    "value": "Asia/Dubai",
                                    "memory_kind": "observation",
                                    "source_backed_clone": True,
                                    "source_backed_predicate": "profile.timezone",
                                    "source_backed_from_conversation_id": "answered-timezone",
                                    "source_backed_from_message_id": "write-timezone",
                                    "source_backed_target_conversation_id": "missing-timezone",
                                },
                            },
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
                            }
                        ],
                        "probes": [],
                    },
                ],
            }
        }
    }
    source_backed_slice_file = tmp_path / "source-backed-slice.json"
    source_backed_slice_file.write_text(json.dumps(source_backed_slice_payload), encoding="utf-8")
    policy_file = tmp_path / "promotion-policy.json"
    policy_file.write_text(
        json.dumps(
            {
                "allowed_promotions": [],
                "deferred_promotions": [],
                "blocked_promotions": [
                    {
                        "policy_decision": "block",
                        "target_conversation_id": "missing-timezone",
                        "predicate": "profile.timezone",
                        "source_conversation_id": "answered-timezone",
                        "source_message_id": "write-timezone",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "policy-aligned-kb"

    payload = cli._build_spark_memory_kb_policy_aligned_slice(
        str(source_backed_slice_file),
        str(policy_file),
        str(output_dir),
    )

    assert payload["summary"]["conversation_count"] == 2
    assert payload["summary"]["accepted_writes"] == 1
    assert payload["summary"]["skipped_turns"] == 1
    assert payload["summary"]["policy_skipped_turn_count"] == 1
    assert payload["summary"]["policy_skipped_by_reason"] == {"block": 1}
    assert payload["compile_result"]["output_dir"] == str(output_dir)

    blocked_support = cli._load_kb_current_state_support(
        str(output_dir),
        subject="human:telegram:missing-timezone",
        predicate="profile.timezone",
    )
    allowed_support = cli._load_kb_current_state_support(
        str(output_dir),
        subject="human:telegram:answered-timezone",
        predicate="profile.timezone",
    )
    assert blocked_support["supporting_evidence_count"] == 0
    assert not blocked_support["value"]
    assert allowed_support["supporting_evidence_count"] == 1
    assert allowed_support["value"] == "Asia/Dubai"


def test_build_spark_memory_kb_refresh_manifest_summarizes_governed_artifact(tmp_path: Path):
    payload = {
        "summary": {
            "conversation_count": 8,
            "accepted_writes": 16,
            "skipped_turns": 3,
            "policy_skipped_turn_count": 3,
            "policy_skipped_by_reason": {"block": 2, "defer": 1},
        },
        "compile_result": {
            "output_dir": "tmp/policy-aligned-kb",
            "snapshot_file": "tmp/policy-aligned-kb/raw/memory-snapshots/latest.json",
            "current_state_page_count": 16,
            "evidence_page_count": 16,
        },
        "health_report": {
            "valid": True,
        },
        "promotion_policy_rows": [
            {
                "policy_decision": "allow",
                "target_conversation_id": "target-1",
                "predicate": "profile.hack_actor",
                "source_conversation_id": "source-1",
                "source_message_id": "msg-1",
                "value": "North Korea",
            },
            {
                "policy_decision": "allow",
                "target_conversation_id": "target-2",
                "predicate": "profile.spark_role",
                "source_conversation_id": "source-1",
                "source_message_id": "msg-2",
                "value": "important part of the rebuild",
            },
            {
                "policy_decision": "defer",
                "target_conversation_id": "target-3",
                "predicate": "profile.timezone",
                "source_conversation_id": "source-1",
                "source_message_id": "msg-3",
                "value": "Asia/Dubai",
            },
            {
                "policy_decision": "block",
                "target_conversation_id": "target-4",
                "predicate": "profile.home_country",
                "source_conversation_id": "source-2",
                "source_message_id": "msg-4",
                "value": "Canada",
            },
        ],
    }
    payload_file = tmp_path / "policy-aligned-slice.json"
    payload_file.write_text(json.dumps(payload), encoding="utf-8")

    manifest = cli._build_spark_memory_kb_refresh_manifest(str(payload_file))

    assert manifest["summary"]["kb_output_dir"] == "tmp/policy-aligned-kb"
    assert manifest["summary"]["snapshot_file"] == "tmp/policy-aligned-kb/raw/memory-snapshots/latest.json"
    assert manifest["summary"]["health_valid"] is True
    assert manifest["summary"]["policy_skipped_by_reason"] == {"block": 2, "defer": 1}
    assert manifest["summary"]["decision_counts"] == {"allow": 2, "block": 1, "defer": 1}
    assert manifest["summary"]["target_conversation_count"] == 4
    assert manifest["summary"]["source_conversation_count"] == 2
    assert manifest["summary"]["source_message_count"] == 4
    assert manifest["policy_targets_by_decision"]["allow"][0]["target_conversation_id"] == "target-1"
    assert manifest["policy_targets_by_decision"]["block"][0]["predicate"] == "profile.home_country"


def test_materialize_spark_memory_kb_refresh_manifest_copies_governed_kb(tmp_path: Path):
    source_kb_dir = tmp_path / "policy-aligned-kb"
    source_snapshot_file = source_kb_dir / "raw" / "memory-snapshots" / "latest.json"
    source_index_file = source_kb_dir / "wiki" / "index.md"
    source_snapshot_file.parent.mkdir(parents=True)
    source_index_file.parent.mkdir(parents=True)
    (source_kb_dir / "CLAUDE.md").write_text("# KB\n", encoding="utf-8")
    source_snapshot_file.write_text('{"current_state":[],"evidence":[],"events":[],"trace":{}}', encoding="utf-8")
    source_index_file.write_text("# Index\n", encoding="utf-8")

    manifest_file = tmp_path / "refresh-manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "summary": {
                    "kb_output_dir": str(source_kb_dir),
                    "snapshot_file": str(source_snapshot_file),
                    "conversation_count": 8,
                    "accepted_writes": 16,
                    "skipped_turns": 3,
                    "policy_skipped_turn_count": 3,
                    "policy_skipped_by_reason": {"block": 2, "defer": 1},
                    "decision_counts": {"allow": 4, "block": 2, "defer": 1},
                    "current_state_page_count": 16,
                    "evidence_page_count": 16,
                },
                "kb": {
                    "output_dir": str(source_kb_dir),
                    "snapshot_file": str(source_snapshot_file),
                },
            }
        ),
        encoding="utf-8",
    )
    materialized_dir = tmp_path / "materialized-kb"

    payload = cli._materialize_spark_memory_kb_refresh_manifest(
        str(manifest_file),
        str(materialized_dir),
    )

    assert payload["summary"]["source_kb_output_dir"] == str(source_kb_dir)
    assert payload["summary"]["materialized_kb_output_dir"] == str(materialized_dir)
    assert payload["summary"]["source_snapshot_file"] == str(source_snapshot_file)
    assert payload["summary"]["materialized_snapshot_file"] == str(
        materialized_dir / "raw" / "memory-snapshots" / "latest.json"
    )
    assert payload["summary"]["decision_counts"] == {"allow": 4, "block": 2, "defer": 1}
    assert payload["summary"]["policy_skipped_by_reason"] == {"block": 2, "defer": 1}
    assert payload["summary"]["health_valid"] is False
    assert (materialized_dir / "CLAUDE.md").exists()
    assert (materialized_dir / "wiki" / "index.md").exists()
    assert (materialized_dir / "raw" / "memory-snapshots" / "latest.json").exists()


def test_publish_spark_memory_kb_refresh_manifest_writes_active_refresh_file(tmp_path: Path):
    source_kb_dir = tmp_path / "policy-aligned-kb"
    source_snapshot_file = source_kb_dir / "raw" / "memory-snapshots" / "latest.json"
    source_index_file = source_kb_dir / "wiki" / "index.md"
    source_snapshot_file.parent.mkdir(parents=True)
    source_index_file.parent.mkdir(parents=True)
    (source_kb_dir / "CLAUDE.md").write_text("# KB\n", encoding="utf-8")
    source_snapshot_file.write_text('{"current_state":[],"evidence":[],"events":[],"trace":{}}', encoding="utf-8")
    source_index_file.write_text("# Index\n", encoding="utf-8")

    manifest_file = tmp_path / "refresh-manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "summary": {
                    "kb_output_dir": str(source_kb_dir),
                    "snapshot_file": str(source_snapshot_file),
                    "conversation_count": 8,
                    "accepted_writes": 16,
                    "skipped_turns": 3,
                    "policy_skipped_turn_count": 3,
                    "policy_skipped_by_reason": {"block": 2, "defer": 1},
                    "decision_counts": {"allow": 4, "block": 2, "defer": 1},
                    "current_state_page_count": 16,
                    "evidence_page_count": 16,
                },
                "kb": {
                    "output_dir": str(source_kb_dir),
                    "snapshot_file": str(source_snapshot_file),
                },
            }
        ),
        encoding="utf-8",
    )
    publish_root = tmp_path / "published"

    payload = cli._publish_spark_memory_kb_refresh_manifest(
        str(manifest_file),
        str(publish_root),
    )

    release_dir = Path(payload["release_output_dir"])
    active_refresh_file = publish_root / "active-refresh.json"
    assert release_dir.parent == publish_root / "releases"
    assert release_dir.name.startswith("spark-kb-")
    assert payload["active_refresh_file"] == str(active_refresh_file)
    assert release_dir.exists()
    assert active_refresh_file.exists()
    active_payload = json.loads(active_refresh_file.read_text(encoding="utf-8"))
    assert active_payload["refresh_manifest_file"] == str(manifest_file)
    assert active_payload["summary"]["materialized_kb_output_dir"] == str(release_dir)
    assert active_payload["summary"]["decision_counts"] == {"allow": 4, "block": 2, "defer": 1}


def test_resolve_spark_memory_kb_active_refresh_reads_published_release(tmp_path: Path):
    kb_dir = tmp_path / "published" / "releases" / "spark-kb-test"
    snapshot_file = kb_dir / "raw" / "memory-snapshots" / "latest.json"
    index_file = kb_dir / "wiki" / "index.md"
    snapshot_file.parent.mkdir(parents=True)
    index_file.parent.mkdir(parents=True)
    (kb_dir / "CLAUDE.md").write_text("# KB\n", encoding="utf-8")
    snapshot_file.write_text('{"current_state":[],"evidence":[],"events":[],"trace":{}}', encoding="utf-8")
    index_file.write_text("# Index\n", encoding="utf-8")
    active_refresh_file = tmp_path / "published" / "active-refresh.json"
    active_refresh_file.write_text(
        json.dumps(
            {
                "summary": {
                    "materialized_kb_output_dir": str(kb_dir),
                    "materialized_snapshot_file": str(snapshot_file),
                    "conversation_count": 8,
                    "accepted_writes": 16,
                    "skipped_turns": 3,
                    "policy_skipped_turn_count": 3,
                    "policy_skipped_by_reason": {"block": 2, "defer": 1},
                    "decision_counts": {"allow": 4, "block": 2, "defer": 1},
                    "current_state_page_count": 16,
                    "evidence_page_count": 16,
                }
            }
        ),
        encoding="utf-8",
    )

    payload = cli._resolve_spark_memory_kb_active_refresh(str(active_refresh_file))

    assert payload["summary"]["kb_output_dir"] == str(kb_dir)
    assert payload["summary"]["snapshot_file"] == str(snapshot_file)
    assert payload["summary"]["health_valid"] is False
    assert payload["summary"]["decision_counts"] == {"allow": 4, "block": 2, "defer": 1}
    assert payload["summary"]["policy_skipped_by_reason"] == {"block": 2, "defer": 1}


def test_read_spark_memory_kb_active_refresh_support_reads_governed_page(tmp_path: Path):
    kb_dir = tmp_path / "published" / "releases" / "spark-kb-test"
    snapshot_file = kb_dir / "raw" / "memory-snapshots" / "latest.json"
    current_state_file = kb_dir / "wiki" / "current-state" / "human-telegram-test-user-profile-hack-actor.md"
    index_file = kb_dir / "wiki" / "index.md"
    snapshot_file.parent.mkdir(parents=True)
    current_state_file.parent.mkdir(parents=True)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    (kb_dir / "CLAUDE.md").write_text("# KB\n", encoding="utf-8")
    snapshot_file.write_text('{"current_state":[],"evidence":[],"events":[],"trace":{}}', encoding="utf-8")
    index_file.write_text("# Index\n", encoding="utf-8")
    current_state_file.write_text(
        "\n".join(
            [
                "---",
                "title: Test",
                "---",
                "# Test",
                "## Value",
                "North Korea",
                "## Supporting Evidence",
                "- [[evidence/test-evidence]]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    active_refresh_file = tmp_path / "published" / "active-refresh.json"
    active_refresh_file.write_text(
        json.dumps(
            {
                "summary": {
                    "materialized_kb_output_dir": str(kb_dir),
                    "materialized_snapshot_file": str(snapshot_file),
                    "conversation_count": 8,
                    "accepted_writes": 16,
                    "skipped_turns": 3,
                    "policy_skipped_turn_count": 3,
                    "policy_skipped_by_reason": {"block": 2, "defer": 1},
                    "decision_counts": {"allow": 4, "block": 2, "defer": 1},
                    "current_state_page_count": 16,
                    "evidence_page_count": 16,
                }
            }
        ),
        encoding="utf-8",
    )

    payload = cli._read_spark_memory_kb_active_refresh_support(
        str(active_refresh_file),
        subject="human:telegram:test-user",
        predicate="profile.hack_actor",
    )

    assert payload["summary"]["kb_output_dir"] == str(kb_dir)
    assert payload["summary"]["found"] is True
    assert payload["summary"]["value"] == "North Korea"
    assert payload["summary"]["supporting_evidence_count"] == 1


def test_verify_spark_memory_kb_active_refresh_policy_reports_honored_rows(tmp_path: Path):
    kb_dir = tmp_path / "published" / "releases" / "spark-kb-test"
    snapshot_file = kb_dir / "raw" / "memory-snapshots" / "latest.json"
    allowed_page = kb_dir / "wiki" / "current-state" / "human-telegram-allowed-profile-hack-actor.md"
    index_file = kb_dir / "wiki" / "index.md"
    snapshot_file.parent.mkdir(parents=True)
    allowed_page.parent.mkdir(parents=True)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    (kb_dir / "CLAUDE.md").write_text("# KB\n", encoding="utf-8")
    snapshot_file.write_text('{"current_state":[],"evidence":[],"events":[],"trace":{}}', encoding="utf-8")
    index_file.write_text("# Index\n", encoding="utf-8")
    allowed_page.write_text(
        "\n".join(
            [
                "---",
                "title: Allowed",
                "---",
                "# Allowed",
                "## Value",
                "North Korea",
                "## Supporting Evidence",
                "- [[evidence/test-evidence]]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    active_refresh_file = tmp_path / "published" / "active-refresh.json"
    active_refresh_file.write_text(
        json.dumps(
            {
                "summary": {
                    "materialized_kb_output_dir": str(kb_dir),
                    "materialized_snapshot_file": str(snapshot_file),
                    "conversation_count": 8,
                    "accepted_writes": 16,
                    "skipped_turns": 3,
                    "policy_skipped_turn_count": 3,
                    "policy_skipped_by_reason": {"block": 2, "defer": 1},
                    "decision_counts": {"allow": 4, "block": 2, "defer": 1},
                    "current_state_page_count": 16,
                    "evidence_page_count": 16,
                }
            }
        ),
        encoding="utf-8",
    )
    policy_aligned_slice_file = tmp_path / "policy-aligned-slice.json"
    policy_aligned_slice_file.write_text(
        json.dumps(
            {
                "promotion_policy_rows": [
                    {
                        "policy_decision": "allow",
                        "target_conversation_id": "allowed-conv",
                        "predicate": "profile.hack_actor",
                    },
                    {
                        "policy_decision": "block",
                        "target_conversation_id": "blocked-conv",
                        "predicate": "profile.timezone",
                    },
                ],
                "normalization": {
                    "normalized": {
                        "conversations": [
                            {
                                "conversation_id": "allowed-conv",
                                "metadata": {"human_id": "human:telegram:allowed"},
                            },
                            {
                                "conversation_id": "blocked-conv",
                                "metadata": {"human_id": "human:telegram:blocked"},
                            },
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    payload = cli._verify_spark_memory_kb_active_refresh_policy(
        str(active_refresh_file),
        str(policy_aligned_slice_file),
    )

    assert payload["summary"]["policy_row_count"] == 2
    assert payload["summary"]["checked_row_count"] == 2
    assert payload["summary"]["violation_count"] == 0
    assert payload["summary"]["policy_honored"] is True
    assert payload["summary"]["honored_counts"] == {"allow": 1, "block": 1}
    assert payload["summary"]["violated_counts"] == {}


def test_read_spark_memory_kb_active_refresh_conversation_support_resolves_subject(tmp_path: Path):
    kb_dir = tmp_path / "published" / "releases" / "spark-kb-test"
    snapshot_file = kb_dir / "raw" / "memory-snapshots" / "latest.json"
    current_state_file = kb_dir / "wiki" / "current-state" / "human-telegram-allowed-profile-hack-actor.md"
    index_file = kb_dir / "wiki" / "index.md"
    snapshot_file.parent.mkdir(parents=True)
    current_state_file.parent.mkdir(parents=True)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    (kb_dir / "CLAUDE.md").write_text("# KB\n", encoding="utf-8")
    snapshot_file.write_text('{"current_state":[],"evidence":[],"events":[],"trace":{}}', encoding="utf-8")
    index_file.write_text("# Index\n", encoding="utf-8")
    current_state_file.write_text(
        "\n".join(
            [
                "---",
                "title: Allowed",
                "---",
                "# Allowed",
                "## Value",
                "North Korea",
                "## Supporting Evidence",
                "- [[evidence/test-evidence]]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    active_refresh_file = tmp_path / "published" / "active-refresh.json"
    active_refresh_file.write_text(
        json.dumps(
            {
                "summary": {
                    "materialized_kb_output_dir": str(kb_dir),
                    "materialized_snapshot_file": str(snapshot_file),
                    "conversation_count": 8,
                    "accepted_writes": 16,
                    "skipped_turns": 3,
                    "policy_skipped_turn_count": 3,
                    "policy_skipped_by_reason": {"block": 2, "defer": 1},
                    "decision_counts": {"allow": 4, "block": 2, "defer": 1},
                    "current_state_page_count": 16,
                    "evidence_page_count": 16,
                }
            }
        ),
        encoding="utf-8",
    )
    policy_aligned_slice_file = tmp_path / "policy-aligned-slice.json"
    policy_aligned_slice_file.write_text(
        json.dumps(
            {
                "normalization": {
                    "normalized": {
                        "conversations": [
                            {
                                "conversation_id": "allowed-conv",
                                "metadata": {"human_id": "human:telegram:allowed"},
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    payload = cli._read_spark_memory_kb_active_refresh_conversation_support(
        str(active_refresh_file),
        str(policy_aligned_slice_file),
        conversation_id="allowed-conv",
        predicate="profile.hack_actor",
    )

    assert payload["conversation_id"] == "allowed-conv"
    assert payload["summary"]["conversation_id"] == "allowed-conv"
    assert payload["summary"]["subject"] == "human:telegram:allowed"
    assert payload["summary"]["found"] is True
    assert payload["summary"]["value"] == "North Korea"


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


def test_build_spark_memory_kb_policy_verdict_labels_action_buckets(tmp_path: Path):
    compare_payload = {
        "summary": {
            "resolved_missing_query_count": 3,
            "resolved_missing_by_action_bucket": {
                "expected_cleanroom_boundary": 1,
                "gauntlet_candidate": 1,
                "regression_candidate": 1,
            },
            "still_unresolved_by_predicate": {},
        },
        "resolved_queries": [
            {
                "conversation_id": "cleanroom-timezone",
                "question": "What is my timezone?",
                "predicate": "profile.timezone",
                "action_bucket": "expected_cleanroom_boundary",
                "answer": "Asia/Dubai",
            },
            {
                "conversation_id": "regression-hack-actor",
                "question": "Who hacked us?",
                "predicate": "profile.hack_actor",
                "action_bucket": "regression_candidate",
                "answer": "North Korea",
            },
            {
                "conversation_id": "gauntlet-timezone",
                "question": "What is my timezone?",
                "predicate": "profile.timezone",
                "action_bucket": "gauntlet_candidate",
                "answer": "Asia/Dubai",
            },
        ],
    }
    compare_file = tmp_path / "compare.json"
    compare_file.write_text(json.dumps(compare_payload), encoding="utf-8")

    payload = cli._build_spark_memory_kb_policy_verdict(str(compare_file))

    assert payload["summary"] == {
        "resolved_missing_query_count": 3,
        "still_unresolved_query_count": 0,
        "action_bucket_count": 3,
    }
    assert payload["policy_verdicts"] == [
        {
            "action_bucket": "expected_cleanroom_boundary",
            "resolved_count": 1,
            "verdict": "retain_boundary_by_default",
            "recommendation": (
                "Keep these lanes abstention-boundary in production unless a product requirement explicitly authorizes "
                "promotion of cleanroom-style facts into the target conversation."
            ),
            "resolved_queries": [
                {
                    "conversation_id": "cleanroom-timezone",
                    "predicate": "profile.timezone",
                    "question": "What is my timezone?",
                    "answer": "Asia/Dubai",
                }
            ],
            "examples": [
                {
                    "conversation_id": "cleanroom-timezone",
                    "predicate": "profile.timezone",
                    "question": "What is my timezone?",
                    "answer": "Asia/Dubai",
                }
            ],
        },
        {
            "action_bucket": "regression_candidate",
            "resolved_count": 1,
            "verdict": "promotable_if_source_path_is_legitimate",
            "recommendation": (
                "These resolved once source evidence was present. Treat them as promotable sourcing candidates and "
                "audit the real upstream path that should write the fact into the target conversation."
            ),
            "resolved_queries": [
                {
                    "conversation_id": "regression-hack-actor",
                    "predicate": "profile.hack_actor",
                    "question": "Who hacked us?",
                    "answer": "North Korea",
                }
            ],
            "examples": [
                {
                    "conversation_id": "regression-hack-actor",
                    "predicate": "profile.hack_actor",
                    "question": "Who hacked us?",
                    "answer": "North Korea",
                }
            ],
        },
        {
            "action_bucket": "gauntlet_candidate",
            "resolved_count": 1,
            "verdict": "expand_coverage_if_product_wants_recall",
            "recommendation": (
                "These resolved with source backing, so the memory/KB layer is capable. Decide whether the gauntlet "
                "lane should gain the same source coverage or intentionally remain sparse."
            ),
            "resolved_queries": [
                {
                    "conversation_id": "gauntlet-timezone",
                    "predicate": "profile.timezone",
                    "question": "What is my timezone?",
                    "answer": "Asia/Dubai",
                }
            ],
            "examples": [
                {
                    "conversation_id": "gauntlet-timezone",
                    "predicate": "profile.timezone",
                    "question": "What is my timezone?",
                    "answer": "Asia/Dubai",
                }
            ],
        },
    ]


def test_build_spark_memory_kb_promotion_plan_joins_policy_and_lineage(tmp_path: Path):
    policy_payload = {
        "policy_verdicts": [
            {
                "action_bucket": "expected_cleanroom_boundary",
                "verdict": "retain_boundary_by_default",
                "recommendation": "keep boundary",
                "resolved_queries": [
                    {
                        "conversation_id": "cleanroom-timezone",
                        "predicate": "profile.timezone",
                        "question": "What is my timezone?",
                        "answer": "Asia/Dubai",
                    }
                ],
                "examples": [
                    {
                        "conversation_id": "cleanroom-timezone",
                        "predicate": "profile.timezone",
                        "question": "What is my timezone?",
                        "answer": "Asia/Dubai",
                    }
                ],
            },
            {
                "action_bucket": "regression_candidate",
                "verdict": "promotable_if_source_path_is_legitimate",
                "recommendation": "promote if legit",
                "resolved_queries": [
                    {
                        "conversation_id": "regression-hack-actor",
                        "predicate": "profile.hack_actor",
                        "question": "Who hacked us?",
                        "answer": "North Korea",
                    }
                ],
                "examples": [
                    {
                        "conversation_id": "regression-hack-actor",
                        "predicate": "profile.hack_actor",
                        "question": "Who hacked us?",
                        "answer": "North Korea",
                    }
                ],
            },
            {
                "action_bucket": "gauntlet_candidate",
                "verdict": "expand_coverage_if_product_wants_recall",
                "recommendation": "optional scope",
                "resolved_queries": [
                    {
                        "conversation_id": "gauntlet-timezone",
                        "predicate": "profile.timezone",
                        "question": "What is my timezone?",
                        "answer": "Asia/Dubai",
                    }
                ],
                "examples": [
                    {
                        "conversation_id": "gauntlet-timezone",
                        "predicate": "profile.timezone",
                        "question": "What is my timezone?",
                        "answer": "Asia/Dubai",
                    }
                ],
            },
        ]
    }
    source_backed_payload = {
        "injected_writes": [
            {
                "predicate": "profile.timezone",
                "target_conversation_id": "cleanroom-timezone",
                "source_conversation_id": "source-timezone",
                "source_message_id": "msg-timezone",
                "cloned_message_id": "clone-timezone",
                "value": "Asia/Dubai",
            },
            {
                "predicate": "profile.hack_actor",
                "target_conversation_id": "regression-hack-actor",
                "source_conversation_id": "source-hack-actor",
                "source_message_id": "msg-hack-actor",
                "cloned_message_id": "clone-hack-actor",
                "value": "North Korea",
            },
            {
                "predicate": "profile.timezone",
                "target_conversation_id": "gauntlet-timezone",
                "source_conversation_id": "source-gauntlet-timezone",
                "source_message_id": "msg-gauntlet-timezone",
                "cloned_message_id": "clone-gauntlet-timezone",
                "value": "Asia/Dubai",
            },
        ]
    }
    policy_file = tmp_path / "policy.json"
    source_backed_file = tmp_path / "source-backed.json"
    policy_file.write_text(json.dumps(policy_payload), encoding="utf-8")
    source_backed_file.write_text(json.dumps(source_backed_payload), encoding="utf-8")

    payload = cli._build_spark_memory_kb_promotion_plan(str(policy_file), str(source_backed_file))

    assert payload["summary"] == {
        "promotable_target_count": 1,
        "optional_target_count": 1,
        "excluded_target_count": 1,
        "missing_lineage_count": 0,
    }
    assert payload["promotable_targets"] == [
        {
            "action_bucket": "regression_candidate",
            "verdict": "promotable_if_source_path_is_legitimate",
            "recommendation": "promote if legit",
            "target_conversation_id": "regression-hack-actor",
            "predicate": "profile.hack_actor",
            "question": "Who hacked us?",
            "answer": "North Korea",
            "source_conversation_id": "source-hack-actor",
            "source_message_id": "msg-hack-actor",
            "cloned_message_id": "clone-hack-actor",
            "value": "North Korea",
        }
    ]
    assert payload["optional_targets"] == [
        {
            "action_bucket": "gauntlet_candidate",
            "verdict": "expand_coverage_if_product_wants_recall",
            "recommendation": "optional scope",
            "target_conversation_id": "gauntlet-timezone",
            "predicate": "profile.timezone",
            "question": "What is my timezone?",
            "answer": "Asia/Dubai",
            "source_conversation_id": "source-gauntlet-timezone",
            "source_message_id": "msg-gauntlet-timezone",
            "cloned_message_id": "clone-gauntlet-timezone",
            "value": "Asia/Dubai",
        }
    ]
    assert payload["excluded_targets"] == [
        {
            "action_bucket": "expected_cleanroom_boundary",
            "verdict": "retain_boundary_by_default",
            "recommendation": "keep boundary",
            "target_conversation_id": "cleanroom-timezone",
            "predicate": "profile.timezone",
            "question": "What is my timezone?",
            "answer": "Asia/Dubai",
            "source_conversation_id": "source-timezone",
            "source_message_id": "msg-timezone",
            "cloned_message_id": "clone-timezone",
            "value": "Asia/Dubai",
        }
    ]
    assert payload["missing_lineage"] == []


def test_build_spark_memory_kb_promotion_plan_uses_full_resolved_queries_not_truncated_examples(
    tmp_path: Path,
):
    policy_payload = {
        "policy_verdicts": [
            {
                "action_bucket": "regression_candidate",
                "verdict": "promotable_if_source_path_is_legitimate",
                "recommendation": "promote if legit",
                "resolved_queries": [
                    {
                        "conversation_id": "regression-hack-actor-1",
                        "predicate": "profile.hack_actor",
                        "question": "Who hacked us?",
                        "answer": "North Korea",
                    },
                    {
                        "conversation_id": "regression-spark-role-1",
                        "predicate": "profile.spark_role",
                        "question": "What role will Spark play in this?",
                        "answer": "important part of the rebuild",
                    },
                    {
                        "conversation_id": "regression-hack-actor-2",
                        "predicate": "profile.hack_actor",
                        "question": "Who hacked us?",
                        "answer": "North Korea",
                    },
                    {
                        "conversation_id": "regression-spark-role-2",
                        "predicate": "profile.spark_role",
                        "question": "What role will Spark play in this?",
                        "answer": "important part of the rebuild",
                    },
                ],
                "examples": [
                    {
                        "conversation_id": "regression-hack-actor-1",
                        "predicate": "profile.hack_actor",
                        "question": "Who hacked us?",
                        "answer": "North Korea",
                    },
                    {
                        "conversation_id": "regression-spark-role-1",
                        "predicate": "profile.spark_role",
                        "question": "What role will Spark play in this?",
                        "answer": "important part of the rebuild",
                    },
                    {
                        "conversation_id": "regression-hack-actor-2",
                        "predicate": "profile.hack_actor",
                        "question": "Who hacked us?",
                        "answer": "North Korea",
                    },
                ],
            }
        ]
    }
    source_backed_payload = {
        "injected_writes": [
            {
                "predicate": "profile.hack_actor",
                "target_conversation_id": "regression-hack-actor-1",
                "source_conversation_id": "source-regression",
                "source_message_id": "msg-hack-1",
                "cloned_message_id": "clone-hack-1",
                "value": "North Korea",
            },
            {
                "predicate": "profile.spark_role",
                "target_conversation_id": "regression-spark-role-1",
                "source_conversation_id": "source-regression",
                "source_message_id": "msg-role-1",
                "cloned_message_id": "clone-role-1",
                "value": "important part of the rebuild",
            },
            {
                "predicate": "profile.hack_actor",
                "target_conversation_id": "regression-hack-actor-2",
                "source_conversation_id": "source-regression",
                "source_message_id": "msg-hack-2",
                "cloned_message_id": "clone-hack-2",
                "value": "North Korea",
            },
            {
                "predicate": "profile.spark_role",
                "target_conversation_id": "regression-spark-role-2",
                "source_conversation_id": "source-regression",
                "source_message_id": "msg-role-2",
                "cloned_message_id": "clone-role-2",
                "value": "important part of the rebuild",
            },
        ]
    }
    policy_file = tmp_path / "policy-full.json"
    source_backed_file = tmp_path / "source-backed-full.json"
    policy_file.write_text(json.dumps(policy_payload), encoding="utf-8")
    source_backed_file.write_text(json.dumps(source_backed_payload), encoding="utf-8")

    payload = cli._build_spark_memory_kb_promotion_plan(str(policy_file), str(source_backed_file))

    assert payload["summary"] == {
        "promotable_target_count": 4,
        "optional_target_count": 0,
        "excluded_target_count": 0,
        "missing_lineage_count": 0,
    }
    assert [
        target["target_conversation_id"] for target in payload["promotable_targets"]
    ] == [
        "regression-hack-actor-1",
        "regression-spark-role-1",
        "regression-hack-actor-2",
        "regression-spark-role-2",
    ]


def test_build_spark_memory_kb_promotion_policy_emits_allow_defer_and_block_rows(tmp_path: Path):
    promotion_plan_payload = {
        "promotable_targets": [
            {
                "action_bucket": "regression_candidate",
                "verdict": "promotable_if_source_path_is_legitimate",
                "recommendation": "promote if legit",
                "target_conversation_id": "regression-hack-actor",
                "predicate": "profile.hack_actor",
                "question": "Who hacked us?",
                "answer": "North Korea",
                "source_conversation_id": "source-regression",
                "source_message_id": "msg-hack-actor",
                "cloned_message_id": "clone-hack-actor",
                "value": "North Korea",
            }
        ],
        "optional_targets": [
            {
                "action_bucket": "gauntlet_candidate",
                "verdict": "expand_coverage_if_product_wants_recall",
                "recommendation": "optional scope",
                "target_conversation_id": "gauntlet-timezone",
                "predicate": "profile.timezone",
                "question": "What is my timezone?",
                "answer": "Asia/Dubai",
                "source_conversation_id": "source-regression",
                "source_message_id": "msg-timezone",
                "cloned_message_id": "clone-timezone",
                "value": "Asia/Dubai",
            }
        ],
        "excluded_targets": [
            {
                "action_bucket": "expected_cleanroom_boundary",
                "verdict": "retain_boundary_by_default",
                "recommendation": "keep boundary",
                "target_conversation_id": "cleanroom-country",
                "predicate": "profile.home_country",
                "question": "What country do I live in?",
                "answer": "Canada",
                "source_conversation_id": "source-regression",
                "source_message_id": "msg-country",
                "cloned_message_id": "clone-country",
                "value": "Canada",
            }
        ],
    }
    promotion_plan_file = tmp_path / "promotion-plan.json"
    promotion_plan_file.write_text(json.dumps(promotion_plan_payload), encoding="utf-8")

    payload = cli._build_spark_memory_kb_promotion_policy(str(promotion_plan_file))

    assert payload["summary"] == {
        "allow_count": 1,
        "defer_count": 1,
        "block_count": 1,
        "include_optional": False,
        "target_conversation_count": 3,
        "source_message_count": 3,
    }
    assert payload["allowed_promotions"] == [
        {
            "policy_decision": "allow",
            "action_bucket": "regression_candidate",
            "verdict": "promotable_if_source_path_is_legitimate",
            "recommendation": "promote if legit",
            "target_conversation_id": "regression-hack-actor",
            "predicate": "profile.hack_actor",
            "question": "Who hacked us?",
            "answer": "North Korea",
            "source_conversation_id": "source-regression",
            "source_message_id": "msg-hack-actor",
            "cloned_message_id": "clone-hack-actor",
            "value": "North Korea",
        }
    ]
    assert payload["deferred_promotions"] == [
        {
            "policy_decision": "defer",
            "action_bucket": "gauntlet_candidate",
            "verdict": "expand_coverage_if_product_wants_recall",
            "recommendation": "optional scope",
            "target_conversation_id": "gauntlet-timezone",
            "predicate": "profile.timezone",
            "question": "What is my timezone?",
            "answer": "Asia/Dubai",
            "source_conversation_id": "source-regression",
            "source_message_id": "msg-timezone",
            "cloned_message_id": "clone-timezone",
            "value": "Asia/Dubai",
        }
    ]
    assert payload["blocked_promotions"] == [
        {
            "policy_decision": "block",
            "action_bucket": "expected_cleanroom_boundary",
            "verdict": "retain_boundary_by_default",
            "recommendation": "keep boundary",
            "target_conversation_id": "cleanroom-country",
            "predicate": "profile.home_country",
            "question": "What country do I live in?",
            "answer": "Canada",
            "source_conversation_id": "source-regression",
            "source_message_id": "msg-country",
            "cloned_message_id": "clone-country",
            "value": "Canada",
        }
    ]

    payload_with_optional = cli._build_spark_memory_kb_promotion_policy(
        str(promotion_plan_file),
        include_optional=True,
    )

    assert payload_with_optional["summary"] == {
        "allow_count": 2,
        "defer_count": 0,
        "block_count": 1,
        "include_optional": True,
        "target_conversation_count": 3,
        "source_message_count": 3,
    }
    assert [row["policy_decision"] for row in payload_with_optional["allowed_promotions"]] == [
        "allow",
        "allow",
    ]
    assert payload_with_optional["deferred_promotions"] == []


def test_build_spark_memory_kb_approved_promotion_slice_filters_to_approved_targets(
    tmp_path: Path, monkeypatch
):
    promotion_plan_payload = {
        "promotable_targets": [
            {
                "target_conversation_id": "regression-hack-actor",
                "source_conversation_id": "source-hack-actor",
                "predicate": "profile.hack_actor",
            }
        ],
        "optional_targets": [
            {
                "target_conversation_id": "gauntlet-timezone",
                "source_conversation_id": "source-gauntlet-timezone",
                "predicate": "profile.timezone",
            }
        ],
        "excluded_targets": [
            {
                "target_conversation_id": "cleanroom-timezone",
                "source_conversation_id": "source-timezone",
                "predicate": "profile.timezone",
            }
        ],
    }
    source_backed_payload = {
        "normalization": {
            "normalized": {
                "source": "spark_builder_state_db",
                "writable_roles": ["user"],
                "conversations": [
                    {"conversation_id": "source-hack-actor", "turns": [], "probes": []},
                    {"conversation_id": "regression-hack-actor", "turns": [], "probes": []},
                    {"conversation_id": "source-gauntlet-timezone", "turns": [], "probes": []},
                    {"conversation_id": "gauntlet-timezone", "turns": [], "probes": []},
                    {"conversation_id": "source-timezone", "turns": [], "probes": []},
                    {"conversation_id": "cleanroom-timezone", "turns": [], "probes": []},
                ],
            }
        }
    }
    promotion_plan_file = tmp_path / "promotion-plan.json"
    source_backed_file = tmp_path / "source-backed.json"
    promotion_plan_file.write_text(json.dumps(promotion_plan_payload), encoding="utf-8")
    source_backed_file.write_text(json.dumps(source_backed_payload), encoding="utf-8")

    replayed_conversation_ids: list[list[str]] = []

    class _FakeSdk:
        def __init__(self, conversation_ids: list[str]):
            self._conversation_ids = conversation_ids

        def export_knowledge_base_snapshot(self) -> dict:
            return {"conversation_ids": list(self._conversation_ids)}

    class _FakeAdapter:
        def __init__(self, conversation_ids: list[str]):
            self.sdk = _FakeSdk(conversation_ids)

    def _fake_execute_shadow_replay_payload(normalized_payload: dict):
        conversation_ids = [
            str(conversation.get("conversation_id") or "")
            for conversation in normalized_payload.get("conversations", [])
            if isinstance(conversation, dict)
        ]
        replayed_conversation_ids.append(conversation_ids)
        return None, _FakeAdapter(conversation_ids)

    monkeypatch.setattr(cli, "_execute_shadow_replay_payload", _fake_execute_shadow_replay_payload)
    monkeypatch.setattr(
        cli,
        "scaffold_spark_knowledge_base",
        lambda output_dir, snapshot, vault_title: {
            "output_dir": str(output_dir),
            "vault_title": vault_title,
            "snapshot": snapshot,
        },
    )
    monkeypatch.setattr(cli, "build_spark_kb_health_report", lambda output_dir: {"valid": True, "output_dir": str(output_dir)})

    payload = cli._build_spark_memory_kb_approved_promotion_slice(
        str(promotion_plan_file),
        str(source_backed_file),
        str(tmp_path / "approved-kb"),
    )

    assert payload["summary"] == {
        "selected_target_count": 1,
        "selected_conversation_count": 2,
        "include_optional": False,
        "missing_conversation_count": 0,
    }
    assert replayed_conversation_ids == [["source-hack-actor", "regression-hack-actor"]]
    assert payload["selected_targets"] == promotion_plan_payload["promotable_targets"]
    assert [
        conversation["conversation_id"]
        for conversation in payload["normalization"]["normalized"]["conversations"]
    ] == ["source-hack-actor", "regression-hack-actor"]
    assert payload["snapshot"] == {"conversation_ids": ["source-hack-actor", "regression-hack-actor"]}
    assert payload["compile_result"]["output_dir"] == str(tmp_path / "approved-kb")
    assert payload["health_report"]["valid"] is True

    payload_with_optional = cli._build_spark_memory_kb_approved_promotion_slice(
        str(promotion_plan_file),
        str(source_backed_file),
        str(tmp_path / "approved-kb-with-optional"),
        include_optional=True,
    )

    assert payload_with_optional["summary"] == {
        "selected_target_count": 2,
        "selected_conversation_count": 4,
        "include_optional": True,
        "missing_conversation_count": 0,
    }
    assert replayed_conversation_ids[-1] == [
        "source-hack-actor",
        "regression-hack-actor",
        "source-gauntlet-timezone",
        "gauntlet-timezone",
    ]
    assert [
        conversation["conversation_id"]
        for conversation in payload_with_optional["normalization"]["normalized"]["conversations"]
    ] == [
        "source-hack-actor",
        "regression-hack-actor",
        "source-gauntlet-timezone",
        "gauntlet-timezone",
    ]
